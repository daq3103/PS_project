import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from slugify import slugify
from sqlalchemy import func, select, text, update

from app.core.deps import has_staff_permission
from app.models.community import AdoptionRequest, CommunityPost
from app.models.rescue import RescueAnimal as Animal
from app.models.rescue import RescueAudit as Audit
from app.models.rescue import RescueCase as Case
from app.models.rescue import RescueEpisode as Episode
from app.models.rescue import RescueEvent as Event
from app.models.rescue import RescueExpense as Expense
from app.models.rescue import RescueFund as Fund
from app.models.rescue import RescueLedger as Ledger
from app.models.rescue import RescueLocation as Location
from app.models.rescue import RescueReceipt as Receipt
from app.models.rescue import RescueTask as Task
from app.models.user import User


def now():
    return datetime.now(UTC)


def code(prefix):
    return prefix + secrets.token_hex(5).upper()


def fail(message, code="STATE_CONFLICT", status=409):
    raise HTTPException(status, {"error_code": code, "message": message})


def manager(user):
    return has_staff_permission(user, "rescue_manage")


def row_dict(row):
    return jsonable_encoder({c.name: getattr(row, c.name) for c in row.__table__.columns})


async def operation(db, scope, key, payload, handler):
    digest = hashlib.sha256(
        json.dumps(jsonable_encoder(payload), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"rescue:{scope}:{key}"},
    )
    old = await db.scalar(select(Receipt).where(Receipt.scope == scope, Receipt.key == key))
    if old:
        if old.digest != digest:
            fail("Yêu cầu đã thay đổi. Vui lòng tải lại và thử lại.", "REQUEST_CONFLICT")
        return old.result
    result = jsonable_encoder(await handler())
    db.add(Receipt(scope=scope, key=key, digest=digest, result=result))
    await db.flush()
    return result


def audit(db, user, resource_id, action, **details):
    db.add(
        Audit(
            actor_id=user.id if user else None,
            resource_id=resource_id,
            action=action,
            details=jsonable_encoder(details),
        )
    )


async def assignee(db, user_id):
    user = await db.get(User, user_id)
    if (
        not user
        or not user.is_active
        or not (manager(user) or has_staff_permission(user, "rescue_care"))
    ):
        fail("Người được giao cần có quyền chăm sóc hoặc quản lý trạm.", "PERMISSION_DENIED", 422)
    return user


async def animal(db, animal_id, user=None, lock=True):
    a = await db.get(Animal, animal_id)
    if not a:
        fail("Không tìm thấy hồ sơ bé.", status=404)
    if lock:
        # Community adoption uses post -> animal, so registry changes follow the same order.
        if a.post_id:
            await db.execute(
                select(CommunityPost.id).where(CommunityPost.id == a.post_id).with_for_update()
            )
        a = await db.scalar(
            select(Animal)
            .where(Animal.id == animal_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    if user and not manager(user):
        assigned = await db.scalar(
            select(Episode.id).where(
                Episode.animal_id == a.id,
                Episode.ended_at.is_(None),
                Episode.assignee_id == user.id,
            )
        )
        task = await db.scalar(
            select(Task.id).where(
                Task.animal_id == a.id,
                Task.assignee_id == user.id,
                Task.status.in_(["todo", "accepted", "in_progress"]),
            )
        )
        if not assigned and not task:
            fail("Không tìm thấy hồ sơ thuộc phần việc của bạn.", "PERMISSION_DENIED", 404)
    return a


async def open_episode(db, animal_id):
    return await db.scalar(
        select(Episode).where(Episode.animal_id == animal_id, Episode.ended_at.is_(None))
    )


async def create_animal(db, user, body):
    if body.post_id:
        post = await db.get(CommunityPost, body.post_id)
        if not post or post.post_type != "adoption":
            fail("Tin liên kết cần là tin nhận nuôi.", status=422)
        if await db.scalar(select(Animal.id).where(Animal.post_id == post.id)):
            fail("Tin này đã gắn với một hồ sơ bé.")
    ident = code("BE-")
    a = Animal(**body.model_dump(), code=ident, slug=slugify(body.name) + "-" + ident.lower())
    db.add(a)
    await db.flush()
    audit(db, user, a.id, "animal_create")
    return row_dict(a)


async def publish_action(db, user, a, body):
    if a.version != body.version:
        fail("Hồ sơ vừa thay đổi. Vui lòng tải lại.", "VERSION_CONFLICT")
    action = body.action
    if action == "open":
        if a.ownership_hold or not await open_episode(db, a.id):
            fail("Cần đợt chăm sóc đang mở và đã rà soát quyền bàn giao.", "ANIMAL_NOT_AVAILABLE")
        if not a.post_id:
            fail("Hãy liên kết tin nhận nuôi trước khi mở nhận hồ sơ.", status=422)
        linked = await db.get(CommunityPost, a.post_id)
        if (
            linked.lifecycle_status != "open"
            or linked.moderation_status != "approved"
            or linked.expires_at <= now()
        ):
            fail("Cần tin nhận nuôi mới đã duyệt và đang mở cho đợt chăm sóc này.")
        a.adoption_state = "open"
    elif action == "pause":
        a.adoption_state = "paused"
    elif action == "hold":
        a.ownership_hold = True
        a.adoption_state = "paused"
    elif action == "release_hold":
        a.ownership_hold = False  # Never automatically reopens adoption.
    elif action == "unpublish":
        a.publication = None
        a.published_at = None
    elif action == "publish":
        events = (
            await db.scalars(
                select(Event)
                .where(Event.animal_id == a.id, Event.public.is_(True))
                .order_by(Event.occurred_at)
                .limit(100)
            )
        ).all()
        a.publication = {
            "name": a.name,
            "species": a.species,
            "sex": a.sex,
            "age_months": a.age_months,
            "story": a.story,
            "care_summary": a.care_summary,
            "public_area": a.public_area,
            "profile": a.profile,
            "timeline": [
                {"note": e.note, "occurred_at": e.occurred_at.isoformat()} for e in events
            ],
        }
        a.published_at = now()
        from app.models.rescue import RescuePublication

        db.add(
            RescuePublication(
                kind="animal",
                resource_id=a.id,
                version=a.version + 1,
                approved_by=user.id,
                payload=a.publication,
            )
        )
    if action == "publish":
        from app.models.rescue_workflow import RescueSubscription
        from app.modules.community.service import notify

        followers = (
            await db.scalars(
                select(RescueSubscription).where(
                    RescueSubscription.animal_id == a.id, RescueSubscription.updates.is_(True)
                )
            )
        ).all()
        for follower in followers:
            await notify(
                db,
                follower.user_id,
                "Bé bạn theo dõi vừa có cập nhật được trạm xác nhận.",
                f"/tram-cuu-ho/be/{a.slug}",
                f"animal-update:{a.id}:{a.version + 1}:{follower.user_id}",
            )
    a.version += 1
    audit(db, user, a.id, "animal_" + action, reason=body.reason, version=a.version)
    await db.flush()
    return row_dict(a)


def public_animal(a, post=None):
    state = a.adoption_state
    if a.ownership_hold:
        state = "paused"
    if post and post.lifecycle_status != "open":
        state = "handed_over" if post.lifecycle_status == "resolved" else "paused"
    from app.modules.community.schemas import CommunityImageOut

    images = (
        [CommunityImageOut.model_validate(img).model_dump() for img in post.images]
        if post and post.moderation_status == "approved"
        else []
    )
    return {
        "id": str(a.id),
        "code": a.code,
        "slug": a.slug,
        **(a.publication or {}),
        "images": images,
        "adoption_state": state,
        "published_at": a.published_at,
        "adoption_slug": post.slug
        if post
        and state == "open"
        and post.moderation_status == "approved"
        and post.expires_at > now()
        else None,
    }


async def capacity(db, location_id, species, started=None):
    loc = await db.scalar(
        select(Location).where(Location.id == location_id).with_for_update(key_share=True)
    )
    if not loc or not loc.active or loc.species not in ("both", species):
        fail("Nơi chăm sóc không phù hợp hoặc đã dừng nhận.", "CAPACITY_FULL")
    current = now()
    if (loc.available_from and current < loc.available_from) or (
        loc.available_until and current >= loc.available_until
    ):
        fail("Nơi chăm sóc chưa có lịch tiếp nhận phù hợp.", "CAPACITY_FULL")
    used = await db.scalar(
        select(func.count())
        .select_from(Episode)
        .where(Episode.location_id == loc.id, Episode.ended_at.is_(None))
    )
    if used >= loc.capacity:
        fail("Nơi chăm sóc đã đủ số lượng được duyệt.", "CAPACITY_FULL")
    return loc


async def intake(db, user, body):
    a = await animal(db, body.animal_id)
    if await open_episode(db, a.id):
        fail("Bé đã có một đợt chăm sóc đang mở.")
    if body.started_at > now() + timedelta(minutes=5):
        fail("Chỉ ghi tiếp nhận đã diễn ra.", status=422)
    await assignee(db, body.assignee_id)
    await capacity(db, body.location_id, a.species)
    if body.case_id and not await db.get(Case, body.case_id):
        fail("Không tìm thấy ca cứu hộ.", status=404)
    episode = Episode(**body.model_dump())
    db.add(episode)
    a.adoption_state = "not_open"
    a.version += 1
    await db.flush()
    db.add(
        Event(
            animal_id=a.id,
            actor_id=user.id,
            kind="intake",
            occurred_at=body.started_at,
            note=body.source_note,
            details={"location_id": str(body.location_id), "episode_id": str(episode.id)},
        )
    )
    audit(db, user, a.id, "intake", episode_id=episode.id)
    return row_dict(episode)


async def transfer(db, user, a, body):
    episode = await open_episode(db, a.id)
    if not episode:
        fail("Bé không có đợt chăm sóc đang mở.")
    await assignee(db, body.assignee_id)
    old = episode.location_id
    for lid in sorted({old, body.location_id}, key=str):
        await db.execute(
            select(Location.id).where(Location.id == lid).with_for_update(key_share=True)
        )
    if old != body.location_id:
        await capacity(db, body.location_id, a.species)
    episode.location_id = body.location_id
    episode.assignee_id = body.assignee_id
    db.add(
        Event(
            animal_id=a.id,
            actor_id=user.id,
            kind="transfer",
            occurred_at=now(),
            note=body.reason,
            details={
                "from": str(old),
                "to": str(body.location_id),
                "assignee_id": str(body.assignee_id),
            },
        )
    )
    from app.models.rescue_workflow import RescueCareSchedule

    await db.execute(
        update(RescueCareSchedule)
        .where(RescueCareSchedule.episode_id == episode.id)
        .values(active=False)
    )
    await db.execute(
        update(Task)
        .where(
            Task.animal_id == a.id,
            Task.episode_id == episode.id,
            Task.status.in_(["todo", "accepted", "in_progress"]),
        )
        .values(status="skipped")
    )
    a.version += 1
    audit(db, user, a.id, "transfer", old=old, new=body.location_id)
    await db.flush()
    return row_dict(episode)


async def close_episode(db, user, a, outcome, reason):
    episode = await open_episode(db, a.id)
    if not episode:
        fail("Không có đợt chăm sóc đang mở.")
    await db.execute(
        select(Location.id)
        .where(Location.id == episode.location_id)
        .with_for_update(key_share=True)
    )
    from app.models.rescue_workflow import RescueCareSchedule

    await db.execute(
        update(RescueCareSchedule)
        .where(RescueCareSchedule.episode_id == episode.id)
        .values(active=False)
    )
    episode.ended_at = now()
    episode.outcome = outcome
    a.adoption_state = "handed_over" if outcome == "adopted" else "paused"
    a.version += 1
    await db.execute(
        update(Task)
        .where(Task.episode_id == episode.id, Task.status.in_(["todo", "accepted", "in_progress"]))
        .values(status="skipped")
    )
    db.add(
        Event(
            animal_id=a.id,
            actor_id=user.id,
            kind="outcome",
            occurred_at=now(),
            note=reason,
            details={"outcome": outcome},
        )
    )
    audit(db, user, a.id, "episode_close", outcome=outcome)
    await db.flush()
    return row_dict(episode)


async def adoption_guard(db, post_id, *, handover=False):
    a = await db.scalar(
        select(Animal)
        .where(Animal.post_id == post_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if a and (
        a.ownership_hold
        or a.adoption_state not in ("open", "matching")
        or not await open_episode(db, a.id)
    ):
        fail(
            "Bé đang tạm dừng nhận nuôi hoặc cần xác minh thông tin. Vui lòng liên hệ trạm.",
            "ANIMAL_NOT_AVAILABLE",
        )
    return a


async def adoption_changed(db, post_id, actor_id, action, request_id):
    a = await db.scalar(select(Animal).where(Animal.post_id == post_id).with_for_update())
    if not a:
        return
    if action in ("withdraw", "reject", "complete"):
        from app.models.rescue_workflow import RescueAppointment

        await db.execute(
            update(RescueAppointment)
            .where(
                RescueAppointment.application_id == request_id,
                RescueAppointment.status.in_(["proposed", "confirmed"]),
                RescueAppointment.starts_at >= now(),
            )
            .values(
                status="cancelled",
                version=RescueAppointment.version + 1,
                change_reason="Hồ sơ nhận nuôi đã kết thúc hoặc thay đổi",
            )
        )
    if action == "approve":
        a.adoption_state = "matching"
    elif action in ("withdraw", "reject") and a.adoption_state == "matching":
        selected = await db.scalar(
            select(AdoptionRequest.id).where(
                AdoptionRequest.post_id == post_id, AdoptionRequest.status == "approved"
            )
        )
        if not selected:
            a.adoption_state = "paused"  # Coordinator must deliberately reopen.
    elif action == "complete":
        episode = await open_episode(db, a.id)
        user = await db.get(User, actor_id)
        if not episode:
            fail("Cần kiểm tra lại đợt chăm sóc trước khi bàn giao.")
        assigned = episode.assignee_id
        await close_episode(db, user, a, "adopted", "Đã xác nhận bàn giao qua hồ sơ nhận nuôi")
        for day in (3, 14, 30):
            db.add(
                Task(
                    animal_id=a.id,
                    assignee_id=assigned,
                    title=f"Đồng hành sau nhận nuôi: mốc {day} ngày",
                    instructions="Liên hệ gia đình để hỏi tình hình và ghi nhận nhu cầu hỗ trợ; không tự kết luận tình trạng y tế.",
                    due_at=now() + timedelta(days=day),
                    occurrence_key=f"followup:{request_id}:{day}",
                )
            )
    a.version += 1
    await db.flush()


async def balances(db, fund_id):
    rows = (
        await db.execute(
            select(Ledger.kind, func.sum(Ledger.amount))
            .where(Ledger.fund_id == fund_id)
            .group_by(Ledger.kind)
        )
    ).all()
    sums = {key: int(amount) for key, amount in rows}
    reserved = int(
        await db.scalar(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                Expense.fund_id == fund_id, Expense.status == "approved"
            )
        )
    )
    from app.models.rescue_workflow import RescueRefund

    pending_refunds = int(
        await db.scalar(
            select(func.coalesce(func.sum(RescueRefund.amount), 0))
            .join(Ledger, RescueRefund.entry_id == Ledger.id)
            .where(Ledger.fund_id == fund_id, RescueRefund.status == "approved")
        )
    )
    cash = (
        sums.get("settled", 0) - sums.get("fee", 0) - sums.get("refund", 0) - sums.get("expense", 0)
    )
    return {
        "confirmed": sums.get("received", 0) - sums.get("refund", 0),
        "settled": sums.get("settled", 0),
        "refunded": sums.get("refund", 0),
        "fees": sums.get("fee", 0),
        "spent": sums.get("expense", 0),
        "committed": reserved,
        "approved_refunds": pending_refunds,
        "available": cash - reserved - pending_refunds,
    }


async def ledger(db, user, fund_id, body):
    fund = await db.scalar(select(Fund).where(Fund.id == fund_id).with_for_update())
    if not fund:
        fail("Không tìm thấy quỹ.", status=404)
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": "external-receipt:" + body.reference},
    )
    from app.models.fulfillment import WebhookEvent

    if await db.scalar(
        select(WebhookEvent.id).where(WebhookEvent.external_event_id == body.reference)
    ):
        fail(
            "Mã giao dịch đã có trong luồng thanh toán Shop. Cần đối soát riêng.",
            "PAYMENT_RECONCILIATION_REQUIRED",
        )
    if await db.scalar(select(Ledger.id).where(Ledger.reference == body.reference)):
        fail("Chứng từ này đã được ghi nhận.")
    if body.kind in ("settled", "refund"):
        original = await db.get(Ledger, body.reverses_id) if body.reverses_id else None
        if not original or original.fund_id != fund_id or original.kind != "received":
            fail("Cần liên kết khoản thu gốc của đúng quỹ.", status=422)
        used = int(
            await db.scalar(
                select(func.coalesce(func.sum(Ledger.amount), 0)).where(
                    Ledger.reverses_id == original.id, Ledger.kind == body.kind
                )
            )
        )
        if used + body.amount > original.amount:
            fail("Số tiền vượt khoản thu gốc còn được xử lý.")
    if body.kind in ("fee", "refund") and (await balances(db, fund_id))["available"] < body.amount:
        fail("Quỹ không đủ số có thể dùng sau các khoản đã cam kết.")
    entry = Ledger(**body.model_dump(), fund_id=fund_id, actor_id=user.id)
    db.add(entry)
    await db.flush()
    audit(db, user, entry.id, "ledger_" + body.kind, fund_id=fund_id, amount=body.amount)
    return row_dict(entry)
