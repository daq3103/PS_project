"""Rescue workflow. Changes, audit and outbox are committed together by callers."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from slugify import slugify
from sqlalchemy import and_, case, func, or_, select, text, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.models.community import (
    AdoptionRequest,
    CommunityAuditLog,
    CommunityJobOutbox,
    CommunityPost,
    CommunityPostImage,
    CommunityReceipt,
    CommunityReport,
    CommunityUpload,
)
from app.modules.community import schemas
from app.modules.community.pet_traits import (
    ACCENTED,
    BREEDS,
    PLAIN,
    canonical_breed,
    expand_search,
    normalize_search,
    search_document,
)

POST_TTL = timedelta(days=30)
ACTIVE_REQUESTS = ("pending", "contacted", "approved")


def now():
    return datetime.now(UTC)


def fail(message: str, code=409):
    raise HTTPException(code, message)


def image_options():
    return selectinload(CommunityPost.images).selectinload(CommunityPostImage.upload)


async def get_post(session, post_id, *, lock=False):
    query = select(CommunityPost).where(CommunityPost.id == post_id).options(image_options())
    if lock:
        query = query.with_for_update(of=CommunityPost).execution_options(populate_existing=True)
    post = await session.scalar(query)
    if not post:
        fail("Không tìm thấy tin", 404)
    return post


async def owner_post(session, post_id, user_id, *, lock=False):
    post = await get_post(session, post_id, lock=lock)
    if post.author_user_id != user_id:
        fail("Không tìm thấy tin", 404)
    return post


async def audit(session, post, actor, action, old=None, new=None, reason=None, request_id=None):
    session.add(
        CommunityAuditLog(
            post_id=post.id,
            actor_user_id=actor,
            action=action,
            old_status=old,
            new_status=new,
            reason=reason,
            request_id=request_id,
        )
    )


async def notify(session, user_id, message, href, key):
    unique_key = hashlib.sha256(key.encode()).hexdigest()
    await session.execute(
        insert(CommunityJobOutbox)
        .values(
            job_type="notification",
            payload={"user_id": str(user_id), "message": message, "href": href},
            unique_key=unique_key,
            status="pending",
            attempt_count=0,
        )
        .on_conflict_do_nothing(index_elements=["unique_key"])
    )


async def receipt(session, user_id, operation, key, payload):
    digest = hashlib.sha256(payload.encode()).hexdigest()
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"community:{user_id}:{operation}:{key}"},
    )
    row = await session.scalar(
        select(CommunityReceipt).where(
            CommunityReceipt.user_id == user_id,
            CommunityReceipt.operation == operation,
            CommunityReceipt.key == key,
        )
    )
    if row and row.payload_hash != digest:
        fail("Mã gửi lại đã được dùng với nội dung khác")
    return row, digest


def save_receipt(session, user_id, operation, key, digest, resource_id):
    session.add(
        CommunityReceipt(
            user_id=user_id,
            operation=operation,
            key=key,
            payload_hash=digest,
            resource_id=resource_id,
        )
    )


async def validate_uploads(session, ids, user_id, allowed_ids=()):
    if len(ids) > 5 or len(ids) != len(set(ids)):
        fail("Tối đa 5 ảnh khác nhau", 422)
    uploads = []
    for upload_id in sorted(ids):
        item = await session.scalar(
            select(CommunityUpload).where(CommunityUpload.id == upload_id).with_for_update()
        )
        if (
            not item
            or (item.uploader_user_id != user_id and item.id not in allowed_ids)
            or item.status != "ready"
        ):
            fail("Ảnh không thuộc về bạn hoặc chưa sẵn sàng", 422)
        uploads.append(item)
    by_id = {u.id: u for u in uploads}
    return [by_id[i] for i in ids]


async def set_images(session, post, uploads):
    post.images.clear()
    await session.flush()
    post.images.extend(
        CommunityPostImage(upload_id=u.id, upload=u, sort_order=i) for i, u in enumerate(uploads)
    )


def validated_post_values(data):
    values = data.model_dump(exclude={"image_upload_ids", "turnstile_token"})
    from app.modules.community.locations import normalize_location

    normalize_location(values)
    values["breed"] = canonical_breed(values.get("breed"), values["pet_type"])
    values["search_text"] = search_document(values)
    return values


async def create_post(session, user_id, data, key, *, adoption=False):
    if (data.post_type == "adoption") != adoption:
        fail("Loại tin không hợp lệ cho endpoint", 403)
    previous, digest = await receipt(
        session, user_id, "post", key, data.model_dump_json(exclude={"turnstile_token"})
    )
    if previous:
        return await owner_post(session, previous.resource_id, user_id)
    uploads = await validate_uploads(session, data.image_upload_ids, user_id)
    post = CommunityPost(
        **validated_post_values(data),
        id=uuid.uuid4(),
        author_user_id=user_id,
        slug=f"{slugify(data.title, max_length=80)}-{uuid.uuid4().hex[:12]}",
        images=[],
        moderation_status="approved" if adoption else "pending",
        lifecycle_status="open",
        expires_at=now() + POST_TTL,
        version=0,
        moderated_by=user_id if adoption else None,
        moderated_at=now() if adoption else None,
    )
    session.add(post)
    await session.flush()
    await set_images(session, post, uploads)
    await audit(session, post, user_id, "create_post", new=post.moderation_status)
    save_receipt(session, user_id, "post", key, digest, post.id)
    await session.flush()
    return post


async def update_post(session, post, user_id, data):
    if post.version != data.version:
        fail("Tin đã thay đổi, vui lòng tải lại")
    if post.post_type == "adoption" and await session.scalar(
        select(AdoptionRequest.id).where(
            AdoptionRequest.post_id == post.id,
            AdoptionRequest.status.in_(("approved", "completed")),
        )
    ):
        fail("Tin đang có người nhận hoặc đã bàn giao; không thể sửa")
    current = {
        name: getattr(post, name)
        for name in schemas.CommunityPostCreateIn.model_fields
        if name not in {"image_upload_ids", "turnstile_token"}
    }
    current.update(data.model_dump(exclude={"version", "image_upload_ids"}, exclude_unset=True))
    try:
        values = validated_post_values(schemas.CommunityPostCreateIn(**current))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    for name, value in values.items():
        setattr(post, name, value)
    if data.image_upload_ids is not None:
        await set_images(
            session,
            post,
            await validate_uploads(
                session,
                data.image_upload_ids,
                user_id,
                allowed_ids={image.upload_id for image in post.images},
            ),
        )
    old = post.moderation_status
    post.moderation_status = "pending"
    post.moderation_reason = None
    post.moderated_at = None
    post.moderated_by = None
    post.version += 1
    post.updated_at = now()
    await audit(session, post, user_id, "edit", old, "pending")
    await session.flush()
    return post


async def get_public_post_by_slug(session, slug, *, lock=False):
    query = (
        select(CommunityPost)
        .where(CommunityPost.slug == slug, CommunityPost.moderation_status == "approved")
        .options(image_options())
    )
    if lock:
        query = query.with_for_update(of=CommunityPost).execution_options(populate_existing=True)
    return await session.scalar(query)


async def list_public_posts(session, filters):
    where = [
        CommunityPost.moderation_status == "approved",
        CommunityPost.lifecycle_status == filters.lifecycle_status,
    ]
    if filters.lifecycle_status == "open":
        where.append(CommunityPost.expires_at > now())
    for name in ("post_type", "province_id", "district_id", "pet_type"):
        value = getattr(filters, name)
        if value is not None:
            where.append(getattr(CommunityPost, name) == value)
    for name in ("coat_length", "pattern", "sex", "size"):
        value = getattr(filters, name)
        if value == "unknown":
            # Historical posts have an empty details object and therefore unknown traits.
            where.append(func.coalesce(CommunityPost.pet_details[name].astext, "unknown") == value)
        elif value is not None:
            where.append(CommunityPost.pet_details.contains({name: value}))
    if filters.colors:
        where.append(CommunityPost.pet_details.contains({"colors": filters.colors.split(",")}))
    if filters.q and filters.q.strip():
        for word in expand_search(filters.q).split():
            where.append(CommunityPost.search_text.contains(word, autoescape=True))
    if filters.breed and filters.breed.strip():
        normalized = expand_search(filters.breed)
        breed = func.translate(func.lower(func.coalesce(CommunityPost.breed, "")), ACCENTED, PLAIN)
        aliases = [normalized]
        for breeds in BREEDS.values():
            for name, alternate in breeds:
                if normalize_search(name) == normalized:
                    aliases.extend(alternate)
        if normalized == "khong ro":
            where.append(or_(breed == "", breed == normalized))
        else:
            where.append(
                or_(
                    breed.in_(aliases),
                    and_(*(breed.contains(word, autoescape=True) for word in normalized.split())),
                )
            )
    # Missing event dates are excluded when the user explicitly filters event dates.
    event = case(
        (CommunityPost.post_type == "adoption", CommunityPost.created_at),
        else_=func.coalesce(CommunityPost.last_seen_at, CommunityPost.found_at),
    )
    zone = ZoneInfo("Asia/Ho_Chi_Minh")
    if filters.date_from:
        where.append(event >= datetime.combine(filters.date_from, datetime.min.time(), zone))
    if filters.date_to:
        where.append(
            event < datetime.combine(filters.date_to, datetime.min.time(), zone) + timedelta(days=1)
        )
    if filters.cursor:
        try:
            stamp, ident = filters.cursor.split(",")
            moment = datetime.fromisoformat(stamp)
            if moment.tzinfo is None:
                raise ValueError()
            where.append(
                tuple_(CommunityPost.created_at, CommunityPost.id) < (moment, uuid.UUID(ident))
            )
        except (ValueError, OverflowError) as exc:
            raise HTTPException(422, "Không tải được trang tiếp theo. Vui lòng tải lại danh sách.") from exc
    rows = list(
        (
            await session.scalars(
                select(CommunityPost)
                .where(*where)
                .options(image_options())
                .order_by(CommunityPost.created_at.desc(), CommunityPost.id.desc())
                .limit(filters.limit + 1)
            )
        ).all()
    )
    next_cursor = None
    if len(rows) > filters.limit:
        rows = rows[: filters.limit]
        next_cursor = f"{rows[-1].created_at.isoformat()},{rows[-1].id}"
    return rows, next_cursor


async def list_my_posts(session, user_id):
    return list(
        (
            await session.scalars(
                select(CommunityPost)
                .where(CommunityPost.author_user_id == user_id)
                .options(image_options())
                .order_by(CommunityPost.created_at.desc())
                .limit(200)
            )
        ).all()
    )


async def reject_active_requests(session, post, actor_id, reason):
    rows = (
        await session.scalars(
            select(AdoptionRequest).where(
                AdoptionRequest.post_id == post.id, AdoptionRequest.status.in_(ACTIVE_REQUESTS)
            )
        )
    ).all()
    for row in rows:
        old = row.status
        row.status = "rejected"
        row.outcome_reason = reason
        row.updated_at = now()
        row.handled_by = actor_id
        await audit(session, post, actor_id, "adoption_reject", old, row.status, reason, row.id)
        await notify(
            session,
            row.user_id,
            "Hồ sơ nhận nuôi đã kết thúc. Xem kết quả trong tài khoản.",
            "/account/adoption-requests",
            f"adoption:{row.id}:rejected:{post.version}",
        )


async def transition_lifecycle(session, post, action, actor_id, reason, version=None):
    if version is not None and post.version != version:
        fail("Tin đã thay đổi, vui lòng tải lại")
    old = post.lifecycle_status
    if action in {"close", "resolve"}:
        if old != "open":
            fail("Tin đã kết thúc")
        if action == "resolve" and post.post_type == "adoption":
            fail("Nhận nuôi chỉ hoàn tất qua xác nhận bàn giao")
        post.lifecycle_status = "closed" if action == "close" else "resolved"
        post.resolved_at = now() if action == "resolve" else None
        post.resolution_note = reason
        if post.post_type == "adoption":
            await reject_active_requests(session, post, actor_id, "Tin nhận nuôi đã đóng")
    elif action == "renew":
        if post.post_type == "adoption" and old == "resolved":
            fail("Bé đã được bàn giao; không thể mở lại")
        if old == "open" and post.expires_at > now() + timedelta(days=3):
            fail("Chỉ xác nhận lại trong 3 ngày trước khi hết hạn")
        post.lifecycle_status = "open"
        post.moderation_status = "pending"
        post.expires_at = now() + POST_TTL
        post.resolved_at = None
        post.resolution_note = None
    else:
        fail("Hành động không hợp lệ", 422)
    post.version += 1
    post.updated_at = now()
    await audit(session, post, actor_id, f"lifecycle_{action}", old, post.lifecycle_status, reason)
    await session.flush()
    return post


async def reveal_contact(session, slug, user_id):
    post = await get_public_post_by_slug(session, slug, lock=True)
    if not post or post.lifecycle_status != "open" or post.expires_at <= now():
        fail("Tin đã kết thúc hoặc không còn công khai", 404)
    await audit(session, post, user_id, "reveal_contact")
    return schemas.ContactRevealOut.model_validate(post, from_attributes=True)


async def report_post(session, post_id, reporter_id, reason):
    post = await get_post(session, post_id, lock=True)
    if post.moderation_status != "approved" or post.author_user_id == reporter_id:
        fail("Không thể báo cáo tin này", 404)
    if await session.scalar(
        select(CommunityReport.id).where(
            CommunityReport.post_id == post_id,
            CommunityReport.reporter_user_id == reporter_id,
            CommunityReport.status == "pending",
        )
    ):
        fail("Bạn đã báo cáo tin này")
    row = CommunityReport(
        post_id=post_id, reporter_user_id=reporter_id, reason=reason, status="pending"
    )
    session.add(row)
    await audit(session, post, reporter_id, "report", new="pending")
    await session.flush()
    return row


async def admin_list_posts(session, qs):
    where = []
    if qs.q:
        where.append(
            or_(
                CommunityPost.title.ilike(f"%{qs.q}%"), CommunityPost.description.ilike(f"%{qs.q}%")
            )
        )
    for name in ("post_type", "moderation_status", "lifecycle_status"):
        if getattr(qs, name):
            where.append(getattr(CommunityPost, name) == getattr(qs, name))
    count = await session.scalar(select(func.count()).select_from(CommunityPost).where(*where))
    rows = list(
        (
            await session.scalars(
                select(CommunityPost)
                .where(*where)
                .options(image_options())
                .order_by(CommunityPost.created_at.desc(), CommunityPost.id.desc())
                .offset(qs.offset)
                .limit(qs.limit)
            )
        ).all()
    )
    return rows, count


async def admin_moderate(session, post, action, moderator_id, reason, version=None):
    if version is not None and post.version != version:
        fail("Tin đã thay đổi, vui lòng tải lại")
    old = post.moderation_status
    target = {"approve": "approved", "reject": "rejected", "hide": "hidden"}.get(action)
    if (
        not target
        or (action in {"approve", "reject"} and old != "pending")
        or (action == "hide" and old != "approved")
    ):
        fail("Trạng thái không cho phép thao tác này")
    if action != "approve" and not (reason or "").strip():
        fail("Cần nhập lý do từ chối hoặc gỡ tin", 422)
    post.moderation_status = target
    post.moderated_by = moderator_id
    post.moderated_at = now()
    post.moderation_reason = reason
    post.version += 1
    post.updated_at = now()
    if action == "approve" and post.lifecycle_status == "open" and post.expires_at <= now():
        post.expires_at = now() + POST_TTL
    if action == "hide" and post.post_type == "adoption":
        await reject_active_requests(session, post, moderator_id, "Tin nhận nuôi đã được gỡ")
    await audit(session, post, moderator_id, f"moderate_{action}", old, target, reason)
    await notify(
        session,
        post.author_user_id,
        f"Tin \"{post.title}\" { {'approved': 'đã được duyệt', 'rejected': 'bị từ chối', 'hidden': 'đã được gỡ'}[target] }.",
        f"/account/community/{post.id}",
        f"post:{post.id}:moderate:{post.version}",
    )
    await session.flush()
    return post


async def admin_handle_report(session, report_id, data, actor_id):
    row = await session.get(CommunityReport, report_id)
    if not row:
        fail("Không tìm thấy báo cáo", 404)
    post = await get_post(session, row.post_id, lock=True)
    await session.refresh(row)
    if row.status != "pending":
        fail("Báo cáo đã xử lý")
    if data.action == "resolved" and post.moderation_status == "approved":
        await admin_moderate(session, post, "hide", actor_id, data.reason)
    row.status = data.action
    row.handled_by = actor_id
    row.handled_at = now()
    await audit(session, post, actor_id, "handle_report", "pending", data.action, data.reason)
    await session.flush()
    return row


def adoption_out(row, *, admin=False):
    values = {
        field: getattr(row, field)
        for field in schemas.AdoptionOut.model_fields
        if field not in {"post_title", "post_slug", "consent"}
    }
    values.update(post_title=row.post.title, post_slug=row.post.slug)
    if admin:
        values.update(user_id=row.user_id, admin_note=row.admin_note, handled_by=row.handled_by)
    return values


async def create_adoption_request(session, post_id, user_id, data, key):
    previous, digest = await receipt(
        session, user_id, "adoption", key, f"{post_id}:{data.model_dump_json()}"
    )
    if previous:
        return await session.get(AdoptionRequest, previous.resource_id)
    post = await get_post(session, post_id, lock=True)
    from app.modules.rescue.service import adoption_guard
    await adoption_guard(session, post_id)
    if post.author_user_id == user_id:
        fail("Không thể đăng ký tin của mình", 403)
    if (
        post.post_type != "adoption"
        or post.moderation_status != "approved"
        or post.lifecycle_status != "open"
        or post.expires_at <= now()
    ):
        fail("Tin không nhận hồ sơ")
    if await session.scalar(
        select(AdoptionRequest.id).where(
            AdoptionRequest.post_id == post_id,
            or_(
                AdoptionRequest.status.in_(("approved", "completed")),
                (AdoptionRequest.user_id == user_id) & AdoptionRequest.status.in_(ACTIVE_REQUESTS),
            ),
        )
    ):
        fail("Đã có hồ sơ đang xử lý hoặc bé đang chờ bàn giao")
    row = AdoptionRequest(
        **data.model_dump(exclude={"consent"}), post_id=post_id, user_id=user_id, status="pending", post=post
    )
    session.add(row)
    await session.flush()
    if data.consent:
        from app.modules.rescue.workflow_service import consent
        await consent(session, user_id, row.id, "adoption", True)
    save_receipt(session, user_id, "adoption", key, digest, row.id)
    await audit(session, post, user_id, "adoption_create", new="pending", request_id=row.id)
    await notify(
        session,
        post.author_user_id,
        "Có hồ sơ nhận nuôi mới cần xem xét.",
        "/admin/community/adoptions",
        f"adoption:{row.id}:new",
    )
    return row


async def adoption_action(session, request_id, actor_id, data=None, *, withdraw=False):
    row = await session.get(AdoptionRequest, request_id)
    if not row or (withdraw and row.user_id != actor_id):
        fail("Không tìm thấy hồ sơ", 404)
    post = await get_post(session, row.post_id, lock=True)
    await session.refresh(row)
    old = row.status
    action = "withdraw" if withdraw else data.action
    target = {
        "withdraw": "withdrawn",
        "contact": "contacted",
        "approve": "approved",
        "complete": "completed",
        "reject": "rejected",
    }[action]
    if target == old:
        return row
    allowed = {
        "withdraw": ACTIVE_REQUESTS,
        "contact": ("pending",),
        "approve": ("contacted",),
        "complete": ("approved",),
        "reject": ACTIVE_REQUESTS,
    }
    if old not in allowed[action]:
        fail("Không thể chuyển trạng thái hồ sơ")
    if action in {"contact", "approve", "complete"} and (
        post.moderation_status != "approved" or post.lifecycle_status != "open"
    ):
        fail("Tin không còn tiếp nhận nhận nuôi")
    if action == "reject" and not (data.reason or "").strip():
        fail("Cần lý do từ chối", 422)
    if action in {"contact", "approve", "complete"}:
        from app.modules.rescue.service import adoption_guard
        await adoption_guard(session, row.post_id)
    if action in {"approve", "complete"}:
        from app.modules.rescue.workflow_service import approval_guard
        await approval_guard(session, row, action)
    if action == "approve" and await session.scalar(
        select(AdoptionRequest.id).where(
            AdoptionRequest.post_id == post.id,
            AdoptionRequest.id != row.id,
            AdoptionRequest.status.in_(("approved", "completed")),
        )
    ):
        fail("Bé đã có người nhận được duyệt")
    row.status = target
    row.updated_at = now()
    if not withdraw:
        row.handled_by = actor_id
        row.admin_note = data.admin_note if data.admin_note is not None else row.admin_note
        row.outcome_reason = data.reason
    await audit(
        session,
        post,
        actor_id,
        f"adoption_{action}",
        old,
        target,
        data.reason if data else None,
        row.id,
    )
    if action == "complete":
        row.completed_at = now()
        post.lifecycle_status = "resolved"
        post.resolved_at = now()
        post.resolution_note = "Đã xác nhận bàn giao"
        post.version += 1
        await session.flush()
        await reject_active_requests(session, post, actor_id, "Bé đã được nhận nuôi")
    await notify(
        session,
        row.user_id,
        "Hồ sơ nhận nuôi đã cập nhật: " + {"withdrawn":"đã rút", "contacted":"đã liên hệ", "approved":"đã duyệt", "completed":"đã bàn giao", "rejected":"chưa phù hợp"}.get(target, "đang xử lý") + ".",
        "/account/adoption-requests",
        f"adoption:{row.id}:{target}",
    )
    await session.flush()
    from app.modules.rescue.service import adoption_changed
    await adoption_changed(session, row.post_id, actor_id, action, row.id)
    return row
