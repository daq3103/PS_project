from datetime import timedelta
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, has_staff_permission
from app.models.community import AdoptionRequest
from app.models.rescue import (
    RescueAnimal,
    RescueEpisode,
    RescueEvent,
    RescueLocation,
    RescueReport,
    RescueSupply,
    RescueTask,
)
from app.models.rescue_workflow import (
    RescueApplicationCheck,
    RescueAppointment,
    RescueCareSchedule,
    RescueConsent,
    RescuePartner,
    RescueShift,
    RescueSubscription,
    RescueSupplyNeed,
    RescueSupplyPledge,
)
from app.models.user import User
from app.modules.rescue import service as svc
from app.modules.rescue import workflow_schemas as s
from app.modules.rescue import workflow_service as ws
from app.modules.rescue.router import manage, mutate
from app.modules.rescue.schemas import CareIn

router = APIRouter(prefix="/api/v1", tags=["rescue-workflows"])


@router.get("/rescue/me/workspace")
async def my_workspace(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    appointments = (
        await db.scalars(
            select(RescueAppointment)
            .where(
                or_(
                    RescueAppointment.participant_id == user.id,
                    RescueAppointment.organizer_id == user.id,
                )
            )
            .order_by(RescueAppointment.starts_at.desc())
            .limit(100)
        )
    ).all()
    partners = (
        await db.scalars(
            select(RescuePartner)
            .where(RescuePartner.user_id == user.id)
            .order_by(RescuePartner.created_at.desc())
            .limit(50)
        )
    ).all()
    staff_scope = svc.manager(user) or has_staff_permission(user, "rescue_care")
    shifts = (
        (
            await db.scalars(
                select(RescueShift)
                .where(or_(RescueShift.assignee_id == user.id, RescueShift.backup_id == user.id))
                .order_by(RescueShift.starts_at.desc())
                .limit(100)
            )
        ).all()
        if staff_scope
        else []
    )
    tasks = (
        (
            await db.scalars(
                select(RescueTask)
                .where(RescueTask.assignee_id == user.id)
                .order_by(RescueTask.due_at.desc())
                .limit(100)
            )
        ).all()
        if staff_scope
        else []
    )
    saved = (
        await db.scalars(
            select(RescueAnimal)
            .join(RescueSubscription)
            .where(RescueSubscription.user_id == user.id, RescueAnimal.publication.isnot(None))
        )
    ).all()
    applications = (
        await db.scalars(
            select(AdoptionRequest)
            .where(AdoptionRequest.user_id == user.id)
            .order_by(AdoptionRequest.created_at.desc())
            .limit(100)
        )
    ).all()
    consents = (
        await db.scalars(select(RescueConsent).where(RescueConsent.user_id == user.id))
    ).all()
    pledges = (
        await db.scalars(
            select(RescueSupplyPledge).where(RescueSupplyPledge.user_id == user.id).limit(100)
        )
    ).all()
    return {
        "appointments": [svc.row_dict(r) for r in appointments],
        "partners": [svc.row_dict(r) for r in partners],
        "shifts": [svc.row_dict(r) for r in shifts],
        "tasks": [svc.row_dict(r) for r in tasks],
        "saved_animals": [
            {"id": a.id, "name": a.publication.get("name"), "slug": a.slug} for a in saved
        ],
        "applications": [
            {"id": a.id, "status": a.status, "created_at": a.created_at, "post_id": a.post_id}
            for a in applications
        ],
        "consents": [svc.row_dict(c) for c in consents],
        "pledges": [svc.row_dict(p) for p in pledges],
    }


@router.get("/admin/rescue/coordination")
async def coordination(user: User = Depends(manage), db: AsyncSession = Depends(get_db)):
    from app.models.rescue_workflow import RescueVisitSlot

    result = {}
    for name, model, order in [
        ("slots", RescueVisitSlot, RescueVisitSlot.starts_at),
        ("appointments", RescueAppointment, RescueAppointment.starts_at),
        ("partners", RescuePartner, RescuePartner.created_at),
        ("shifts", RescueShift, RescueShift.starts_at),
        ("checks", RescueApplicationCheck, RescueApplicationCheck.created_at),
        ("pledges", RescueSupplyPledge, RescueSupplyPledge.created_at),
        ("needs", RescueSupplyNeed, RescueSupplyNeed.created_at),
        ("schedules", RescueCareSchedule, RescueCareSchedule.next_at),
    ]:
        result[name] = [
            svc.row_dict(r)
            for r in (await db.scalars(select(model).order_by(order.desc()).limit(200))).all()
        ]
    from app.models.rescue_workflow import RescueMessage

    threads = (
        await db.execute(
            select(User.id, User.full_name)
            .join(RescueMessage, RescueMessage.resource_id == User.id)
            .where(RescueMessage.resource_kind == "support")
            .distinct()
            .limit(200)
        )
    ).all()
    result["support_threads"] = [{"id": ident, "name": name} for ident, name in threads]
    result["applications"] = [
        {
            "id": a.id,
            "user_id": a.user_id,
            "name": a.applicant_name,
            "status": a.status,
            "post_id": a.post_id,
        }
        for a in (
            await db.scalars(
                select(AdoptionRequest).order_by(AdoptionRequest.created_at.desc()).limit(200)
            )
        ).all()
    ]
    result["staff"] = [
        {"id": u.id, "name": u.full_name}
        for u in (
            await db.scalars(
                select(User).where(
                    User.is_active.is_(True),
                    or_(
                        User.role == "owner",
                        User.staff_permissions.contains(["rescue_manage"]), User.staff_permissions.contains(["platform_manage"]),
                        User.staff_permissions.contains(["rescue_care"]),
                    ),
                )
            )
        ).all()
    ]
    result["animals"] = [
        {
            "id": a.id,
            "name": a.name,
            "version": a.version,
            "profile": a.profile,
            "post_id": a.post_id,
        }
        for a in (
            await db.scalars(
                select(RescueAnimal).order_by(RescueAnimal.created_at.desc()).limit(200)
            )
        ).all()
    ]
    return result


@router.post("/admin/rescue/appointments", status_code=201)
async def appointment(
    body: s.AppointmentIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await mutate(
        db, user, "appointment", key, body, lambda: ws.create_appointment(db, user, body)
    )


@router.post("/rescue/appointments/{ident}/action")
async def appointment_action(
    ident: UUID,
    body: s.AppointmentAction,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ws.appointment_action(db, user, ident, body)


@router.get("/rescue/applications/{ident}/review")
async def application_review(
    ident: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    row = await ws.application(db, ident, user)
    check = await db.scalar(
        select(RescueApplicationCheck).where(RescueApplicationCheck.application_id == row.id)
    )
    # Applicant sees only agreement and handover evidence, never staff verification notes.
    return (
        svc.row_dict(check)
        if check and svc.manager(user)
        else {
            "agreement": check.agreement if check else "",
            "verified": bool(check and check.verified_at),
            "handover_at": check.handover_at if check else None,
        }
    )


@router.post("/admin/rescue/applications/{ident}/check")
async def application_check(
    ident: UUID, body: s.CheckIn, user: User = Depends(manage), db: AsyncSession = Depends(get_db)
):
    return await ws.check_application(db, await ws.application(db, ident, user, True), user, body)


@router.post("/rescue/consents/{resource_id}")
async def set_consent(
    resource_id: UUID,
    body: s.ConsentIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.purpose == "adoption":
        row = await db.get(AdoptionRequest, resource_id)
        if not row or row.user_id != user.id:
            svc.fail("Không tìm thấy hồ sơ của bạn.", status=404)
    elif body.purpose == "updates":
        if not await db.get(RescueAnimal, resource_id):
            svc.fail("Không tìm thấy hồ sơ bé.", status=404)
        subscription = await db.scalar(
            select(RescueSubscription)
            .where(
                RescueSubscription.user_id == user.id, RescueSubscription.animal_id == resource_id
            )
            .with_for_update()
        )
        if subscription:
            subscription.updates = body.allowed
    else:
        from app.models.rescue_workflow import RescueAsset

        asset = await db.get(RescueAsset, resource_id)
        if not asset or asset.uploader_id != user.id:
            svc.fail("Không tìm thấy ảnh thuộc quyền của bạn.", status=404)
        if not body.allowed:
            asset.public = False
            asset.publication_allowed = False
    return svc.row_dict(await ws.consent(db, user.id, resource_id, body.purpose, body.allowed))


@router.post("/rescue/partners", status_code=201)
async def register_partner(
    body: s.PartnerIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    async def create():
        if body.available_until <= svc.now():
            svc.fail("Thời gian sẵn sàng đã qua.", status=422)
        if (
            await db.scalar(
                select(func.count())
                .select_from(RescuePartner)
                .where(RescuePartner.user_id == user.id, RescuePartner.status == "pending")
            )
            >= 5
        ):
            svc.fail("Bạn đã có nhiều đăng ký chờ duyệt. Vui lòng cập nhật với trạm.")
        row = RescuePartner(**body.model_dump(exclude={"consent"}), user_id=user.id)
        db.add(row)
        await db.flush()
        await ws.consent(db, user.id, row.id, "participation", True)
        return svc.row_dict(row)

    return await mutate(db, user, "partner", key, body, create)


@router.post("/rescue/partners/{ident}/action")
async def partner_action(
    ident: UUID,
    body: s.DecisionIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ws.partner_action(db, user, ident, body)


@router.post("/admin/rescue/shifts", status_code=201)
async def create_shift(
    body: s.ShiftIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    async def create():
        await svc.assignee(db, body.assignee_id)
        await svc.assignee(db, body.backup_id)
        if body.assignee_id == body.backup_id or body.ends_at - body.starts_at > timedelta(
            hours=24
        ):
            svc.fail("Ca tối đa 24 giờ và cần người dự phòng khác người trực.", status=422)
        await ws.lock(db, "shift:" + str(body.assignee_id))
        if await db.scalar(
            select(RescueShift.id).where(
                RescueShift.assignee_id == body.assignee_id,
                RescueShift.status.in_(["scheduled", "accepted"]),
                RescueShift.starts_at < body.ends_at,
                RescueShift.ends_at > body.starts_at,
            )
        ):
            svc.fail("Người trực đã có ca trùng giờ.")
        row = RescueShift(**body.model_dump())
        db.add(row)
        await db.flush()
        svc.audit(db, user, row.id, "shift_create")
        return svc.row_dict(row)

    return await mutate(db, user, "shift", key, body, create)


@router.post("/rescue/shifts/{ident}/action")
async def shift_action(
    ident: UUID,
    body: s.ShiftAction,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.scalar(select(RescueShift).where(RescueShift.id == ident).with_for_update())
    if not row or (not svc.manager(user) and user.id not in (row.assignee_id, row.backup_id)):
        svc.fail("Không tìm thấy ca trực của bạn.", status=404)
    if row.version != body.version or row.status in ("completed", "cancelled"):
        svc.fail("Ca trực vừa thay đổi hoặc đã kết thúc.", "VERSION_CONFLICT")
    if body.action == "cancel" and not svc.manager(user):
        svc.fail("Cần điều phối xác nhận phương án khi hủy ca.", "PERMISSION_DENIED", 403)
    row.status = {"accept": "accepted", "handover": "completed", "cancel": "cancelled"}[body.action]
    row.handover, row.version = body.note, row.version + 1
    svc.audit(db, user, row.id, "shift_" + body.action, note=body.note)
    await db.flush()
    return svc.row_dict(row)


@router.post("/admin/rescue/care-schedules", status_code=201)
async def schedule(
    body: s.ScheduleIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    async def create():
        await svc.animal(db, body.animal_id)
        episode = await svc.open_episode(db, body.animal_id)
        if (
            not episode
            or body.until_at < body.next_at
            or body.until_at > svc.now() + timedelta(days=366)
        ):
            svc.fail("Cần đợt chăm sóc đang mở và khoảng lặp hợp lệ tối đa một năm.", status=422)
        row = RescueCareSchedule(episode_id=episode.id, **body.model_dump(exclude={"animal_id"}))
        db.add(row)
        await db.flush()
        svc.audit(db, user, row.id, "care_schedule_create")
        return svc.row_dict(row)

    return await mutate(db, user, "care-schedule", key, body, create)


@router.post("/admin/rescue/care-schedules/{ident}/stop")
async def stop_schedule(
    ident: UUID, user: User = Depends(manage), db: AsyncSession = Depends(get_db)
):
    row = await db.scalar(
        select(RescueCareSchedule).where(RescueCareSchedule.id == ident).with_for_update()
    )
    if not row:
        svc.fail("Không tìm thấy lịch chăm sóc.", status=404)
    row.active = False
    await db.execute(
        update(RescueTask)
        .where(
            RescueTask.occurrence_key.like(f"care:{row.id}:%"),
            RescueTask.due_at > svc.now(),
            RescueTask.status.in_(["todo", "accepted", "in_progress"]),
        )
        .values(status="skipped")
    )
    svc.audit(db, user, row.id, "care_schedule_stop")
    return {"stopped": True}


@router.post("/rescue/animals/{ident}/follow")
async def follow(
    ident: UUID,
    body: s.ConsentIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    a = await db.get(RescueAnimal, ident)
    if not a or not a.publication or body.purpose != "updates":
        svc.fail("Hồ sơ chưa sẵn sàng để theo dõi.", status=404)
    await ws.lock(db, f"follow:{user.id}:{ident}")
    row = await db.scalar(
        select(RescueSubscription).where(
            RescueSubscription.user_id == user.id, RescueSubscription.animal_id == ident
        )
    )
    if not row:
        row = RescueSubscription(user_id=user.id, animal_id=ident, updates=body.allowed)
        db.add(row)
    else:
        row.updates = body.allowed
    await ws.consent(db, user.id, ident, "updates", body.allowed)
    return {"saved": True, "updates": body.allowed}


@router.delete("/rescue/animals/{ident}/follow")
async def unfollow(
    ident: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    row = await db.scalar(
        select(RescueSubscription)
        .where(RescueSubscription.user_id == user.id, RescueSubscription.animal_id == ident)
        .with_for_update()
    )
    if row:
        await db.delete(row)
    await ws.consent(db, user.id, ident, "updates", False)
    return {"saved": False}


@router.patch("/admin/rescue/animals/{ident}/profile")
async def profile(
    ident: UUID, body: s.ProfileIn, user: User = Depends(manage), db: AsyncSession = Depends(get_db)
):
    a = await svc.animal(db, ident)
    if a.version != body.version:
        svc.fail("Hồ sơ vừa thay đổi. Vui lòng tải lại.", "VERSION_CONFLICT")
    if body.video_url:
        url = urlparse(body.video_url)
        if url.scheme != "https" or url.hostname not in (
            "www.youtube.com",
            "youtube.com",
            "youtu.be",
            "www.tiktok.com",
            "www.facebook.com",
            "facebook.com",
        ):
            svc.fail("Dùng đường dẫn HTTPS từ YouTube, TikTok hoặc Facebook.", status=422)
    if body.behavior and not body.observed_at:
        svc.fail("Quan sát hành vi cần ghi thời điểm thực tế.", status=422)
    if body.observed_at and body.observed_at > svc.now() + timedelta(minutes=5):
        svc.fail("Thời điểm quan sát chưa diễn ra.", status=422)
    a.profile = body.model_dump(mode="json", exclude={"version"})
    a.version += 1
    svc.audit(db, user, a.id, "animal_profile_edit", version=a.version)
    return svc.row_dict(a)


@router.get("/admin/rescue/supply-stock")
async def stock(user: User = Depends(manage), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(select(RescueSupply).order_by(RescueSupply.created_at.desc()).limit(200))
    ).all()
    return [{**svc.row_dict(r), **await ws.supply_stock(db, r)} for r in rows]


@router.post("/admin/rescue/supplies/{ident}/movement", status_code=201)
async def movement(
    ident: UUID,
    body: s.SupplyMovementIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await mutate(
        db, user, "stock:" + str(ident), key, body, lambda: ws.move_supply(db, user, ident, body)
    )


@router.get("/rescue/supply-needs")
async def needs(db: AsyncSession = Depends(get_db)):
    return [
        svc.row_dict(r)
        for r in (
            await db.scalars(
                select(RescueSupplyNeed)
                .where(RescueSupplyNeed.status == "open")
                .order_by(RescueSupplyNeed.created_at.desc())
                .limit(100)
            )
        ).all()
    ]


@router.post("/admin/rescue/supply-needs", status_code=201)
async def need(
    body: s.NeedIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    async def create():
        row = RescueSupplyNeed(**body.model_dump())
        db.add(row)
        await db.flush()
        return svc.row_dict(row)

    return await mutate(db, user, "need", key, body, create)


@router.post("/admin/rescue/supply-needs/{ident}/close")
async def close_need(ident: UUID, user: User = Depends(manage), db: AsyncSession = Depends(get_db)):
    row = await db.get(RescueSupplyNeed, ident)
    if not row:
        svc.fail("Không tìm thấy nhu cầu.", status=404)
    row.status = "closed"
    svc.audit(db, user, ident, "supply_need_close")
    return {"closed": True}


@router.post("/rescue/supply-pledges", status_code=201)
async def pledge(
    body: s.PledgeIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    async def create():
        need = await db.get(RescueSupplyNeed, body.need_id)
        if not need or need.status != "open":
            svc.fail("Trạm đã dừng nhận đăng ký cho nhu cầu này.")
        if body.shop_order_id:
            from app.models.commerce import Order

            order = await db.scalar(
                select(Order)
                .where(Order.id == body.shop_order_id, Order.user_id == user.id)
                .with_for_update()
            )
            if not order or order.status in ("cancelled", "refunded"):
                svc.fail("Chọn đơn Shop của bạn chưa hủy/hoàn.", status=422)
            if await db.scalar(
                select(RescueSupplyPledge.id).where(RescueSupplyPledge.shop_order_id == order.id)
            ):
                svc.fail("Đơn Shop đã gắn đăng ký tặng trạm khác.")
        row = RescueSupplyPledge(**body.model_dump(), user_id=user.id)
        db.add(row)
        await db.flush()
        return svc.row_dict(row)

    return await mutate(db, user, "pledge", key, body, create)


@router.post("/rescue/supply-pledges/{ident}/action")
async def pledge_action(
    ident: UUID,
    body: s.PledgeAction,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    async def action():
        row = await db.scalar(
            select(RescueSupplyPledge).where(RescueSupplyPledge.id == ident).with_for_update()
        )
        if not row or (not svc.manager(user) and row.user_id != user.id):
            svc.fail("Không tìm thấy đăng ký hiện vật của bạn.", status=404)
        if row.version != body.version or row.status in ("received", "cancelled"):
            svc.fail("Đăng ký vừa thay đổi hoặc đã kết thúc.", "VERSION_CONFLICT")
        if body.action == "receive":
            if not svc.manager(user):
                svc.fail("Người phụ trách trạm xác nhận lượng thực nhận.", "PERMISSION_DENIED", 403)
            if (
                body.quantity <= 0
                or body.accepted_quantity > body.quantity
                or (body.accepted_quantity and body.expiry_at and body.expiry_at <= svc.now())
            ):
                svc.fail("Kiểm tra số thực nhận, dùng được và hạn dùng.", status=422)
            if await db.scalar(
                select(RescueSupply.id).where(RescueSupply.reference == body.reference)
            ):
                svc.fail("Biên nhận đã được ghi ở lô hiện vật khác.")
            if row.shop_order_id:
                from app.models.commerce import Order

                order = await db.get(Order, row.shop_order_id)
                if order.status != "delivered" or order.payment_status != "paid":
                    svc.fail(
                        "Đơn Shop chưa giao và thanh toán hoàn tất. Nếu hàng thực tế đã tới, cần đối chiếu Shop trước khi ghi nhận tặng."
                    )
            need = await db.get(RescueSupplyNeed, row.need_id)
            receipt = RescueSupply(
                name=need.title,
                unit=need.unit,
                quantity=body.quantity,
                accepted_quantity=body.accepted_quantity,
                reference=body.reference,
                expiry_at=body.expiry_at,
                note=body.note,
                actor_id=user.id,
            )
            db.add(receipt)
            await db.flush()
            row.receipt_id, row.status = receipt.id, "received"
        elif body.action == "ship":
            if row.status != "pledged":
                svc.fail("Hiện vật đã có trạng thái vận chuyển.")
            await ws.lock(db, "tracking:" + body.reference)
            if await db.scalar(
                select(RescueSupplyPledge.id).where(
                    RescueSupplyPledge.tracking_reference == body.reference
                )
            ):
                svc.fail("Vận đơn đã gắn đăng ký khác.")
            row.tracking_reference, row.status = body.reference, "in_transit"
        else:
            if row.status == "in_transit" and not svc.manager(user):
                svc.fail("Hàng đang giao cần trạm xác nhận phương án xử lý trước khi hủy.")
            row.status = "cancelled"
        row.version += 1
        svc.audit(db, user, row.id, "pledge_" + body.action, note=body.note)
        await db.flush()
        return svc.row_dict(row)

    return await mutate(db, user, "pledge-action:" + str(ident), key, body, action)


@router.get("/admin/rescue/activity-report")
async def activity_report(
    start: s.AwareDatetime = Query(),
    end: s.AwareDatetime = Query(),
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    if end <= start or end - start > timedelta(days=366):
        svc.fail("Chọn kỳ báo cáo tối đa một năm.", status=422)

    async def count(model, *clauses):
        return int(await db.scalar(select(func.count()).select_from(model).where(*clauses)))

    outcomes = dict(
        (
            await db.execute(
                select(RescueEpisode.outcome, func.count())
                .where(RescueEpisode.ended_at >= start, RescueEpisode.ended_at < end)
                .group_by(RescueEpisode.outcome)
            )
        ).all()
    )
    # Return-rate denominator is the same cohort of confirmed adoption episodes, not monthly totals.
    cohort = (
        await db.scalars(
            select(RescueEpisode).where(
                RescueEpisode.outcome == "adopted",
                RescueEpisode.ended_at >= start,
                RescueEpisode.ended_at < end,
            )
        )
    ).all()
    returned = 0
    matured_returned = 0
    matured = [e for e in cohort if e.ended_at + timedelta(days=30) <= svc.now()]
    for episode in cohort:
        has_return = bool(
            await db.scalar(
                select(RescueEpisode.id).where(
                    RescueEpisode.animal_id == episode.animal_id,
                    RescueEpisode.started_at > episode.ended_at,
                    RescueEpisode.started_at <= episode.ended_at + timedelta(days=30),
                )
            )
        )
        returned += has_return
        matured_returned += has_return and episode in matured
    return {
        "period": {
            "start": start,
            "end_exclusive": end,
            "timezone": "Asia/Ho_Chi_Minh",
            "as_of": svc.now(),
        },
        "sources": {
            "reports": "rescue_reports.created_at",
            "cases": "rescue_cases.created_at",
            "intakes": "rescue_episodes.started_at",
            "outcomes": "rescue_episodes.ended_at",
            "occupancy": "open rescue_episodes at query time",
        },
        "reports": await count(
            RescueReport, RescueReport.created_at >= start, RescueReport.created_at < end
        ),
        "cases": await _case_count(db, start, end),
        "intake_episodes": await count(
            RescueEpisode, RescueEpisode.started_at >= start, RescueEpisode.started_at < end
        ),
        "distinct_animals": int(
            await db.scalar(
                select(func.count(func.distinct(RescueEpisode.animal_id))).where(
                    RescueEpisode.started_at >= start, RescueEpisode.started_at < end
                )
            )
        ),
        "currently_in_care": await count(RescueEpisode, RescueEpisode.ended_at.is_(None)),
        "currently_fostered": int(
            await db.scalar(
                select(func.count())
                .select_from(RescueEpisode)
                .join(RescueLocation)
                .where(RescueEpisode.ended_at.is_(None), RescueLocation.kind == "foster")
            )
        ),
        "outcomes": outcomes,
        "overdue_tasks": await count(
            RescueTask,
            RescueTask.status.in_(["todo", "accepted", "in_progress"]),
            RescueTask.due_at < svc.now(),
        ),
        "care_duration_days_closed": float(
            await db.scalar(
                select(
                    func.coalesce(
                        func.avg(
                            func.extract("epoch", RescueEpisode.ended_at - RescueEpisode.started_at)
                        )
                        / 86400,
                        0,
                    )
                ).where(RescueEpisode.ended_at >= start, RescueEpisode.ended_at < end)
            )
        ),
        "return_cohort_30_days": {
            "adoptions": len(cohort),
            "returned": returned,
            "matured": len(matured),
            "matured_returned": matured_returned,
            "rate": matured_returned / len(matured) if matured else None,
        },
        "trial_visits": await count(
            RescueAppointment,
            RescueAppointment.kind == "trial",
            RescueAppointment.status == "completed",
            RescueAppointment.starts_at >= start,
            RescueAppointment.starts_at < end,
        ),
    }


async def _case_count(db, start, end):
    from app.models.rescue import RescueCase

    return int(
        await db.scalar(
            select(func.count())
            .select_from(RescueCase)
            .where(RescueCase.created_at >= start, RescueCase.created_at < end)
        )
    )


@router.post("/admin/rescue/animals/{ident}/public-updates", status_code=201)
async def public_update(
    ident: UUID,
    body: s.PublicUpdateIn,
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    await svc.animal(db, ident)
    if body.occurred_at > svc.now() + timedelta(minutes=5):
        svc.fail("Thời điểm cập nhật chưa diễn ra.", status=422)
    event = RescueEvent(
        animal_id=ident,
        actor_id=user.id,
        kind="public_update",
        occurred_at=body.occurred_at,
        note=body.note,
        public=True,
    )
    db.add(event)
    await db.flush()
    svc.audit(db, user, event.id, "public_update_draft")
    return {"id": str(event.id), "notice": "Mốc sẽ hiện khi duyệt công bố lại hồ sơ bé."}


@router.post("/admin/rescue/visit-slots", status_code=201)
async def create_slot(
    body: s.VisitSlotIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    async def create():
        from app.models.rescue_workflow import RescueVisitSlot

        await svc.animal(db, body.animal_id)
        await svc.assignee(db, body.organizer_id)
        if body.starts_at <= svc.now():
            svc.fail("Khung gặp mới cần ở tương lai.", status=422)
        await ws.calendar_free(db, body.organizer_id, body.starts_at, body.ends_at)
        row = RescueVisitSlot(**body.model_dump())
        db.add(row)
        await db.flush()
        svc.audit(db, user, row.id, "visit_slot_create")
        return svc.row_dict(row)

    return await mutate(db, user, "visit-slot", key, body, create)


@router.get("/rescue/visit-slots")
async def visit_slots(db: AsyncSession = Depends(get_db)):
    from app.models.rescue_workflow import RescueVisitSlot

    slots = (
        await db.scalars(
            select(RescueVisitSlot)
            .where(
                RescueVisitSlot.active.is_(True),
                RescueVisitSlot.appointment_id.is_(None),
                RescueVisitSlot.starts_at > svc.now(),
            )
            .order_by(RescueVisitSlot.starts_at)
            .limit(100)
        )
    ).all()
    result = []
    for slot in slots:
        a = await db.get(RescueAnimal, slot.animal_id)
        if (
            not a
            or not a.publication
            or a.ownership_hold
            or a.adoption_state not in ("open", "matching")
        ):
            continue
        occupied = await db.scalar(
            select(RescueAppointment.id).where(
                RescueAppointment.organizer_id == slot.organizer_id,
                RescueAppointment.status.in_(["proposed", "confirmed"]),
                RescueAppointment.starts_at < slot.ends_at,
                RescueAppointment.ends_at > slot.starts_at,
            )
        )
        if not occupied:
            result.append(
                {
                    "id": slot.id,
                    "starts_at": slot.starts_at,
                    "ends_at": slot.ends_at,
                    "animal_name": a.publication["name"],
                    "animal_id": a.id,
                    "post_id": a.post_id,
                }
            )
    return result


@router.post("/rescue/visit-slots/{ident}/book", status_code=201)
async def book_slot(
    ident: UUID,
    body: s.SlotBookingIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    async def create():
        from app.models.rescue_workflow import RescueVisitSlot

        slot = await db.scalar(
            select(RescueVisitSlot).where(RescueVisitSlot.id == ident).with_for_update()
        )
        if not slot or not slot.active or slot.appointment_id or slot.starts_at <= svc.now():
            svc.fail("Khung giờ đã được chọn hoặc không còn nhận lịch.", "PLACEMENT_CONFLICT")
        app = await ws.application(db, body.application_id, user)
        if app.user_id != user.id:
            svc.fail("Chỉ đặt lịch cho hồ sơ của bạn.", "PERMISSION_DENIED", 403)
        animal = await svc.animal(db, slot.animal_id)
        if not animal.post_id:
            svc.fail("Bé chưa liên kết hồ sơ nhận nuôi.", status=422)
        await svc.adoption_guard(db, animal.post_id)
        if animal.adoption_state == "matching" and app.status != "approved":
            svc.fail(
                "Bé đang ghép với gia đình được duyệt. Vui lòng trao đổi lại với trạm.",
                "ANIMAL_NOT_AVAILABLE",
            )
        result = await ws.create_appointment(
            db,
            user,
            s.AppointmentIn(
                animal_id=slot.animal_id,
                application_id=app.id,
                organizer_id=slot.organizer_id,
                participant_id=user.id,
                starts_at=slot.starts_at,
                ends_at=slot.ends_at,
                kind="visit",
                location=slot.location,
            ),
        )
        slot.appointment_id = UUID(result["id"])
        return result

    return await mutate(db, user, "slot-book:" + str(ident), key, body, create)


@router.post("/admin/rescue/visit-slots/{ident}/close")
async def close_slot(ident: UUID, user: User = Depends(manage), db: AsyncSession = Depends(get_db)):
    from app.models.rescue_workflow import RescueVisitSlot

    row = await db.scalar(
        select(RescueVisitSlot).where(RescueVisitSlot.id == ident).with_for_update()
    )
    if not row:
        svc.fail("Không tìm thấy khung giờ.", status=404)
    row.active = False
    svc.audit(db, user, row.id, "visit_slot_close")
    return {"closed": True}


@router.put("/rescue/partners/{ident}")
async def update_partner(
    ident: UUID,
    body: s.PartnerUpdateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.scalar(select(RescuePartner).where(RescuePartner.id == ident).with_for_update())
    if not row or row.user_id != user.id:
        svc.fail("Không tìm thấy đăng ký của bạn.", status=404)
    if row.version != body.version or row.status not in ("pending", "approved", "pending_update"):
        svc.fail("Đăng ký đã thay đổi hoặc đang dừng. Vui lòng tải lại.", "VERSION_CONFLICT")
    if body.kind != row.kind or body.available_until <= svc.now():
        svc.fail("Giữ loại đăng ký hiện có và chọn thời gian tương lai.", status=422)
    row.proposed_update = body.model_dump(mode="json", exclude={"version", "consent"})
    row.status = "pending_update" if row.location_id else "pending"
    row.version += 1
    svc.audit(db, user, row.id, "partner_propose_update")
    return svc.row_dict(row)


async def foster_animals(db, user, animal_id=None):
    stmt = (
        select(RescueAnimal)
        .join(RescueEpisode, RescueEpisode.animal_id == RescueAnimal.id)
        .join(RescuePartner, RescuePartner.location_id == RescueEpisode.location_id)
        .where(
            RescuePartner.user_id == user.id,
            RescuePartner.status.in_(["approved", "pending_update"]),
            RescueEpisode.ended_at.is_(None),
        )
    )
    if animal_id:
        stmt = stmt.where(RescueAnimal.id == animal_id)
    return (await db.scalars(stmt)).all()


@router.get("/rescue/me/foster-animals")
async def my_foster_animals(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    rows = await foster_animals(db, user)
    return [
        {
            "id": a.id,
            "name": a.name,
            "code": a.code,
            "care_summary": a.publication.get("care_summary", "") if a.publication else "",
        }
        for a in rows
    ]


@router.post("/rescue/foster-animals/{ident}/journal", status_code=201)
async def foster_journal(
    ident: UUID,
    body: CareIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    async def create():
        await svc.animal(db, ident)
        if not await foster_animals(db, user, ident):
            svc.fail("Bé không thuộc nhà chăm sóc tạm của bạn.", "PERMISSION_DENIED", 403)
        if (
            body.kind not in ("observation", "care", "weight")
            or body.occurred_at > svc.now() + timedelta(minutes=5)
            or body.supersedes_id
        ):
            svc.fail(
                "Chỉ ghi quan sát, chăm sóc hoặc cân nặng thực tế; hồ sơ chuyên môn do trạm xác minh.",
                status=422,
            )
        event = RescueEvent(
            animal_id=ident,
            actor_id=user.id,
            kind="foster_" + body.kind,
            occurred_at=body.occurred_at,
            note=body.note,
            public=False,
        )
        db.add(event)
        await db.flush()
        svc.audit(db, user, event.id, "foster_journal")
        return {"id": str(event.id)}

    return await mutate(db, user, "foster-journal:" + str(ident), key, body, create)


@router.get("/admin/rescue/recovery-review")
async def recovery_review(user: User = Depends(manage), db: AsyncSession = Depends(get_db)):
    from app.models.commerce import Order
    from app.models.rescue_workflow import RescueDonationEvent

    gifts = (
        await db.execute(
            select(RescueSupplyPledge.id, Order.order_code)
            .join(Order, Order.id == RescueSupplyPledge.shop_order_id)
            .where(
                RescueSupplyPledge.status == "received",
                or_(
                    Order.status.in_(["cancelled", "refunded"]), Order.payment_status == "refunded"
                ),
            )
        )
    ).all()
    return {
        "gift_order_exceptions": [
            {
                "pledge_id": ident,
                "order_code": code,
                "action": "Kiểm tra hàng đã tặng, hàng hoàn và chứng từ Shop; không tự đảo tồn hiện vật thực nhận.",
            }
            for ident, code in gifts
        ],
        "unassigned_open_episodes": int(
            await db.scalar(
                select(func.count())
                .select_from(RescueEpisode)
                .join(User, User.id == RescueEpisode.assignee_id)
                .where(
                    RescueEpisode.ended_at.is_(None),
                    or_(
                        User.is_active.is_(False),
                        ~or_(
                            User.role == "owner",
                            User.staff_permissions.contains(["rescue_manage"]), User.staff_permissions.contains(["platform_manage"]),
                            User.staff_permissions.contains(["rescue_care"]),
                        ),
                    ),
                )
            )
        ),
        "pending_transfer_exceptions": int(
            await db.scalar(
                select(func.count())
                .select_from(RescueDonationEvent)
                .where(
                    RescueDonationEvent.status.notin_(
                        ["matched", "matched_resolved", "resolved_hold", "refund_requested"]
                    )
                )
            )
        ),
        "as_of": svc.now(),
    }


@router.post("/admin/rescue/animals/{ident}/responsibility")
async def responsibility(
    ident: UUID,
    body: s.ResponsibilityIn,
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    a = await svc.animal(db, ident)
    await svc.assignee(db, body.assignee_id)
    episode = await svc.open_episode(db, ident)
    if not episode:
        svc.fail("Không có đợt chăm sóc đang mở.")
    if episode.assignee_id == body.assignee_id:
        return {"assignee_id": str(body.assignee_id)}
    old = episode.assignee_id
    await db.execute(
        update(RescueCareSchedule)
        .where(RescueCareSchedule.episode_id == episode.id)
        .values(active=False)
    )
    await db.execute(
        update(RescueTask)
        .where(
            RescueTask.episode_id == episode.id,
            RescueTask.status.in_(["todo", "accepted", "in_progress"]),
        )
        .values(status="skipped")
    )
    episode.assignee_id = body.assignee_id
    a.version += 1
    db.add(
        RescueEvent(
            animal_id=ident,
            actor_id=user.id,
            kind="responsibility",
            occurred_at=svc.now(),
            note=body.reason,
            details={"from": str(old), "to": str(body.assignee_id)},
            public=False,
        )
    )
    svc.audit(
        db,
        user,
        ident,
        "responsibility_handover",
        old=old,
        new=body.assignee_id,
        reason=body.reason,
    )
    await db.flush()
    return {"assignee_id": str(body.assignee_id)}
