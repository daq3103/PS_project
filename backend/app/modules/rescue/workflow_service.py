"""Transactional rescue workflows; reminders are deduplicated in the same DB transaction."""

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert

from app.models.community import AdoptionRequest
from app.models.rescue import RescueAnimal, RescueEpisode, RescueReport, RescueSupply, RescueTask
from app.models.rescue_workflow import (
    RescueApplicationCheck,
    RescueAppointment,
    RescueCareSchedule,
    RescueConsent,
    RescuePartner,
    RescueReminder,
    RescueShift,
    RescueSupplyMovement,
)
from app.models.user import User
from app.modules.rescue import service as svc


async def lock(db, key):
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": "rescue-workflow:" + key},
    )


async def consent(db, user_id, resource_id, purpose, allowed):
    await lock(db, f"consent:{user_id}:{resource_id}:{purpose}")
    row = await db.scalar(
        select(RescueConsent).where(
            RescueConsent.user_id == user_id,
            RescueConsent.resource_id == resource_id,
            RescueConsent.purpose == purpose,
        )
    )
    if not row:
        row = RescueConsent(
            user_id=user_id,
            resource_id=resource_id,
            purpose=purpose,
            policy_version="rescue-v1",
            allowed=allowed,
            changed_at=svc.now(),
        )
        db.add(row)
    else:
        row.allowed, row.changed_at = allowed, svc.now()
    await db.flush()
    svc.audit(
        db,
        None,
        resource_id,
        "consent_change",
        user_id=user_id,
        purpose=purpose,
        allowed=allowed,
        version="rescue-v1",
    )
    return row


async def application(db, application_id, user, manager_only=False):
    row = await db.get(AdoptionRequest, application_id)
    if not row or (not svc.manager(user) and (manager_only or row.user_id != user.id)):
        svc.fail("Không tìm thấy hồ sơ trong phạm vi của bạn.", "PERMISSION_DENIED", 404)
    return row


async def check_application(db, row, user, body):
    await lock(db, "application:" + str(row.id))
    check = await db.scalar(
        select(RescueApplicationCheck).where(RescueApplicationCheck.application_id == row.id)
    )
    if not check:
        check = RescueApplicationCheck(application_id=row.id)
        db.add(check)
    if body.action == "verify":
        check.verified_at, check.verified_by = svc.now(), user.id
        check.contact_method, check.verification_note = body.contact_method, body.note
    elif body.action == "agreement":
        if not check.verified_at:
            svc.fail("Cần xác minh liên hệ trước khi ghi điều kiện bàn giao.")
        check.agreement = body.note
    else:
        if row.status != "approved" or not check.verified_at or not check.agreement:
            svc.fail("Cần hồ sơ đã duyệt, liên hệ đã xác minh và điều kiện bàn giao.")
        check.handover_at, check.handover_by, check.recipient_confirmed = svc.now(), user.id, True
    svc.audit(db, user, row.id, "application_" + body.action, note=body.note)
    await db.flush()
    return svc.row_dict(check)


async def approval_guard(db, row, action):
    # Community-only posts keep their original workflow. Shelter placements require evidence.
    if not await db.scalar(select(RescueAnimal.id).where(RescueAnimal.post_id == row.post_id)):
        return
    check = await db.scalar(
        select(RescueApplicationCheck).where(RescueApplicationCheck.application_id == row.id)
    )
    agreed = await db.scalar(
        select(RescueConsent.id).where(
            RescueConsent.user_id == row.user_id,
            RescueConsent.resource_id == row.id,
            RescueConsent.purpose == "adoption",
            RescueConsent.allowed.is_(True),
        )
    )
    if not check or not check.verified_at or not agreed:
        svc.fail(
            "Cần xác minh liên hệ và sự đồng ý của người nhận nuôi trước khi duyệt.",
            "APPLICATION_STATE_CONFLICT",
        )
    if action == "complete" and (
        not check.agreement or not check.handover_at or not check.recipient_confirmed
    ):
        svc.fail(
            "Cần ghi biên bản và xác nhận bàn giao thực tế trước khi hoàn tất.",
            "APPLICATION_STATE_CONFLICT",
        )


async def calendar_free(db, person, start, end, excluding=None):
    if end <= start or end - start > timedelta(hours=8):
        svc.fail("Lịch cần có giờ kết thúc sau bắt đầu và không dài quá 8 giờ.", status=422)
    await lock(db, "calendar:" + str(person))
    stmt = select(RescueAppointment.id).where(
        RescueAppointment.organizer_id == person,
        RescueAppointment.status.in_(["proposed", "confirmed"]),
        RescueAppointment.starts_at < end,
        RescueAppointment.ends_at > start,
    )
    if excluding:
        stmt = stmt.where(RescueAppointment.id != excluding)
    if await db.scalar(stmt):
        svc.fail("Người phụ trách đã có lịch trong khung giờ này.", "PLACEMENT_CONFLICT")


async def create_appointment(db, user, body):
    await svc.assignee(db, body.organizer_id)
    participant = await db.get(User, body.participant_id)
    if not participant or not participant.is_active:
        svc.fail("Người tham gia chưa có tài khoản hoạt động.", status=422)
    await svc.animal(db, body.animal_id)
    if body.starts_at < svc.now():
        svc.fail("Lịch mới phải ở tương lai.", status=422)
    if body.application_id:
        app = await application(db, body.application_id, user)
        animal = await db.get(RescueAnimal, body.animal_id)
        if (
            app.user_id != body.participant_id
            or app.post_id != animal.post_id
            or app.status not in ("pending", "contacted", "approved")
        ):
            svc.fail("Hồ sơ nhận nuôi không khớp lịch hẹn.", status=422)
    await calendar_free(db, body.organizer_id, body.starts_at, body.ends_at)
    row = RescueAppointment(**body.model_dump())
    db.add(row)
    await db.flush()
    from app.modules.community.service import notify

    await notify(
        db,
        row.participant_id,
        "Trạm đề xuất một lịch hẹn. Vui lòng xác nhận.",
        "/account/rescue",
        f"appointment:{row.id}:new",
    )
    svc.audit(db, user, row.id, "appointment_create")
    return svc.row_dict(row)


async def appointment_action(db, user, ident, body):
    # Organizer lock precedes row lock, including reschedules, matching creation.
    existing = await db.get(RescueAppointment, ident)
    if not existing or (
        not svc.manager(user) and user.id not in (existing.organizer_id, existing.participant_id)
    ):
        svc.fail("Không tìm thấy lịch hẹn của bạn.", status=404)
    await lock(db, "calendar:" + str(existing.organizer_id))
    row = await db.scalar(
        select(RescueAppointment)
        .where(RescueAppointment.id == ident)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row.version != body.version or row.status in ("cancelled", "completed"):
        svc.fail("Lịch đã thay đổi hoặc kết thúc. Vui lòng tải lại.", "VERSION_CONFLICT")
    if (
        body.action in ("reschedule", "complete")
        and not svc.manager(user)
        and user.id != row.organizer_id
    ):
        svc.fail("Chỉ người phụ trách cập nhật lịch này.", "PERMISSION_DENIED", 403)
    if body.action == "reschedule":
        if not body.starts_at or not body.ends_at or body.starts_at < svc.now():
            svc.fail("Cần khung giờ mới trong tương lai.", status=422)
        await calendar_free(db, row.organizer_id, body.starts_at, body.ends_at, row.id)
        row.starts_at, row.ends_at, row.status = body.starts_at, body.ends_at, "proposed"
    elif body.action == "complete":
        if row.status != "confirmed" or row.starts_at > svc.now():
            svc.fail("Chỉ hoàn tất lịch đã xác nhận và đã tới giờ.")
        row.status = "completed"
    elif body.action == "confirm":
        if row.ends_at <= svc.now():
            svc.fail("Lịch đã qua. Vui lòng liên hệ để đổi giờ.")
        row.status = "confirmed"
    else:
        row.status = "cancelled"
    row.change_reason, row.version = body.reason, row.version + 1
    from app.modules.community.service import notify

    for person in {row.organizer_id, row.participant_id}:
        await notify(
            db,
            person,
            "Lịch hẹn với trạm vừa cập nhật.",
            "/account/rescue",
            f"appointment:{row.id}:v{row.version}:{person}",
        )
    svc.audit(
        db, user, row.id, "appointment_" + body.action, reason=body.reason, version=row.version
    )
    await db.flush()
    return svc.row_dict(row)


async def partner_action(db, user, ident, body):
    row = await db.scalar(select(RescuePartner).where(RescuePartner.id == ident).with_for_update())
    if not row or (not svc.manager(user) and (row.user_id != user.id or body.action != "withdraw")):
        svc.fail("Không tìm thấy đăng ký trong phạm vi của bạn.", status=404)
    if row.version != body.version:
        svc.fail("Đăng ký vừa thay đổi. Vui lòng tải lại.", "VERSION_CONFLICT")
    if body.action == "approve":
        effective_until = (
            datetime.fromisoformat(row.proposed_update["available_until"])
            if row.proposed_update
            else row.available_until
        )
        if (
            row.status not in ("pending", "paused", "pending_update")
            or effective_until <= svc.now()
        ):
            svc.fail("Hồ sơ không còn thời gian sẵn sàng phù hợp.")
        if row.proposed_update:
            proposed = dict(row.proposed_update)
            if row.location_id:
                from app.models.rescue import RescueLocation

                location = await db.scalar(
                    select(RescueLocation)
                    .where(RescueLocation.id == row.location_id)
                    .with_for_update(key_share=True)
                )
                occupied = int(
                    await db.scalar(
                        select(func.count())
                        .select_from(RescueEpisode)
                        .where(
                            RescueEpisode.location_id == location.id,
                            RescueEpisode.ended_at.is_(None),
                        )
                    )
                )
                if proposed["capacity"] < occupied:
                    svc.fail("Cần bàn giao bớt bé trước khi giảm sức chứa.")
                location.capacity = proposed["capacity"]
                location.species = proposed["species"]
                location.private_contact = (
                    proposed["contact"] + "\n" + proposed["area"] + "\n" + proposed["conditions"]
                )
                location.available_from = datetime.fromisoformat(proposed["available_from"])
                location.available_until = datetime.fromisoformat(proposed["available_until"])
                species = (
                    await db.scalars(
                        select(RescueAnimal.species)
                        .join(RescueEpisode)
                        .where(
                            RescueEpisode.location_id == location.id,
                            RescueEpisode.ended_at.is_(None),
                        )
                    )
                ).all()
                if location.species != "both" and any(
                    value != location.species for value in species
                ):
                    svc.fail("Không đổi loại bé nhận khi vẫn đang chăm sóc loài khác.")
            for key, value in proposed.items():
                setattr(
                    row,
                    key,
                    datetime.fromisoformat(value)
                    if key in ("available_from", "available_until")
                    else value,
                )
            row.proposed_update = {}
        if row.kind == "foster" and not row.location_id:
            from app.models.rescue import RescueLocation

            loc = RescueLocation(
                name=row.name,
                kind="foster",
                species=row.species,
                capacity=row.capacity,
                private_contact=row.contact + "\n" + row.area + "\n" + row.conditions,
                available_from=row.available_from,
                available_until=row.available_until,
            )
            db.add(loc)
            await db.flush()
            row.location_id = loc.id
        row.status = "approved"
    elif body.action == "reject" and row.status == "pending_update":
        row.proposed_update = {}
        row.status = "approved"
    else:
        if row.location_id:
            from app.models.rescue import RescueLocation

            loc = await db.scalar(
                select(RescueLocation)
                .where(RescueLocation.id == row.location_id)
                .with_for_update(key_share=True)
            )
            if await db.scalar(
                select(RescueEpisode.id).where(
                    RescueEpisode.location_id == loc.id, RescueEpisode.ended_at.is_(None)
                )
            ):
                svc.fail(
                    "Nhà tạm đang có bé. Cần bàn giao sang người phụ trách khác trước khi dừng."
                )
            loc.active = False
        row.status = {"pause": "paused", "reject": "rejected", "withdraw": "withdrawn"}[body.action]
    if row.location_id and row.status == "approved":
        from app.models.rescue import RescueLocation

        (await db.get(RescueLocation, row.location_id)).active = True
    row.decision_note, row.version = body.reason, row.version + 1
    svc.audit(db, user, row.id, "partner_" + body.action, reason=body.reason)
    await db.flush()
    return svc.row_dict(row)


async def supply_stock(db, receipt):
    rows = (
        await db.execute(
            select(RescueSupplyMovement.kind, func.sum(RescueSupplyMovement.quantity))
            .where(RescueSupplyMovement.receipt_id == receipt.id)
            .group_by(RescueSupplyMovement.kind)
        )
    ).all()
    sums = dict(rows)
    held = int(
        receipt.quantity
        - receipt.accepted_quantity
        + sums.get("quarantine", 0)
        - sums.get("release", 0)
        - sums.get("dispose", 0)
    )
    used = int(sums.get("use", 0))
    available = (
        receipt.accepted_quantity
        - used
        - int(sums.get("quarantine", 0))
        + int(sums.get("release", 0))
    )
    return {
        "usable": available if not receipt.expiry_at or receipt.expiry_at > svc.now() else 0,
        "quarantined": held,
        "used": used,
        "disposed": int(sums.get("dispose", 0)),
        "expired": bool(receipt.expiry_at and receipt.expiry_at <= svc.now()),
        "unexpired_balance": available,
    }


async def move_supply(db, user, ident, body):
    receipt = await db.scalar(
        select(RescueSupply).where(RescueSupply.id == ident).with_for_update()
    )
    if not receipt:
        svc.fail("Không tìm thấy lô hiện vật.", status=404)
    stock = await supply_stock(db, receipt)
    if body.kind in ("use", "quarantine"):
        limit = stock["usable"] if body.kind == "use" else stock["unexpired_balance"]
    else:
        limit = stock["quarantined"]
        if body.kind == "release" and stock["expired"]:
            svc.fail("Không đưa hàng hết hạn trở lại dùng được.")
    if body.quantity > limit:
        svc.fail("Số lượng vượt phần hiện vật còn phù hợp.", "STOCK_CONFLICT")
    if await db.scalar(
        select(RescueSupplyMovement.id).where(RescueSupplyMovement.reference == body.reference)
    ):
        svc.fail("Mã phiếu hiện vật đã được sử dụng.")
    row = RescueSupplyMovement(receipt_id=ident, actor_id=user.id, **body.model_dump())
    db.add(row)
    await db.flush()
    svc.audit(db, user, row.id, "supply_" + body.kind, receipt_id=ident, quantity=body.quantity)
    return svc.row_dict(row)


async def remind(db, resource, key, recipients, message):
    result = await db.execute(
        insert(RescueReminder)
        .values(id=uuid4(), resource_id=resource, occurrence_key=key, sent_at=svc.now())
        .on_conflict_do_nothing(index_elements=["occurrence_key"])
        .returning(RescueReminder.id)
    )
    if not result.scalar_one_or_none():
        return 0
    from app.modules.community.service import notify

    for recipient in set(recipients):
        await notify(db, recipient, message, "/account/rescue", f"{key}:{recipient}")
    return 1


async def maintenance(db):
    if not await db.scalar(
        text("SELECT pg_try_advisory_xact_lock(hashtextextended('rescue:maintenance',0))")
    ):
        return {"busy": True}
    now = svc.now()
    managers = (
        await db.scalars(
            select(User.id).where(
                User.is_active.is_(True),
                or_(User.role == "owner", User.staff_permissions.contains(["rescue_manage"]), User.staff_permissions.contains(["platform_manage"])),
            )
        )
    ).all()
    count = 0
    schedules = (
        await db.scalars(
            select(RescueCareSchedule)
            .where(
                RescueCareSchedule.active.is_(True),
                RescueCareSchedule.next_at <= now + timedelta(days=1),
            )
            .order_by(RescueCareSchedule.next_at)
            .limit(30)
            .with_for_update(skip_locked=True)
        )
    ).all()
    for schedule in schedules:
        episode = await db.get(RescueEpisode, schedule.episode_id)
        if not episode or episode.ended_at or schedule.next_at > schedule.until_at:
            schedule.active = False
            continue
        # Bound catch-up work; unique occurrence keys survive retries and worker restarts.
        for _ in range(7):
            due = schedule.next_at
            if due > now + timedelta(days=1) or due > schedule.until_at:
                break
            await db.execute(
                insert(RescueTask)
                .values(
                    id=uuid4(),
                    animal_id=episode.animal_id,
                    episode_id=episode.id,
                    assignee_id=episode.assignee_id,
                    title=schedule.title,
                    instructions=schedule.instructions,
                    due_at=due,
                    status="todo",
                    occurrence_key=f"care:{schedule.id}:{due.isoformat()}",
                )
                .on_conflict_do_nothing(index_elements=["occurrence_key"])
            )
            schedule.next_at += timedelta(days=schedule.interval_days)
    tasks = (
        await db.scalars(
            select(RescueTask)
            .where(
                RescueTask.status.in_(["todo", "accepted", "in_progress"]),
                RescueTask.due_at <= now + timedelta(hours=1),
            )
            .order_by(RescueTask.due_at)
            .limit(100)
        )
    ).all()
    for task in tasks:
        episode = await db.get(RescueEpisode, task.episode_id) if task.episode_id else None
        if task.episode_id and (
            not episode or episode.ended_at or episode.assignee_id != task.assignee_id
        ):
            task.status = "skipped"
            continue
        overdue = task.due_at < now - timedelta(hours=1)
        count += await remind(
            db,
            task.id,
            f"task:{task.id}:{'overdue' if overdue else 'due'}",
            [task.assignee_id, *managers] if overdue else [task.assignee_id],
            "Có công việc chăm sóc cần kiểm tra."
            if not overdue
            else "Có công việc chăm sóc quá hạn cần người phụ trách kiểm tra.",
        )
    appointments = (
        await db.scalars(
            select(RescueAppointment)
            .where(
                RescueAppointment.status == "confirmed",
                RescueAppointment.starts_at > now,
                RescueAppointment.starts_at <= now + timedelta(hours=24),
            )
            .limit(100)
            .with_for_update(skip_locked=True)
        )
    ).all()
    for appointment in appointments:
        count += await remind(
            db,
            appointment.id,
            f"appointment:{appointment.id}:v{appointment.version}",
            [appointment.organizer_id, appointment.participant_id],
            "Bạn có lịch hẹn đã xác nhận với trạm trong 24 giờ tới.",
        )
    shifts = (
        await db.scalars(
            select(RescueShift)
            .where(
                RescueShift.status.in_(["scheduled", "accepted"]),
                RescueShift.starts_at <= now + timedelta(hours=1),
                RescueShift.ends_at > now,
            )
            .limit(100)
        )
    ).all()
    for shift in shifts:
        count += await remind(
            db,
            shift.id,
            f"shift:{shift.id}:v{shift.version}",
            [shift.assignee_id, shift.backup_id],
            "Vui lòng kiểm tra ca trực và người nhận bàn giao.",
        )
    reports = (
        await db.scalars(
            select(RescueReport)
            .where(
                RescueReport.status.in_(["new", "verifying", "assigned"]),
                RescueReport.acknowledged_at.is_(None),
                RescueReport.created_at < now - timedelta(minutes=30),
            )
            .limit(100)
        )
    ).all()
    backups = [s.backup_id for s in shifts if s.starts_at <= now]
    for report in reports:
        count += await remind(
            db,
            report.id,
            f"report:{report.id}:unacknowledged:v{report.version}",
            [*managers, *backups],
            "Có tin báo chưa được xác nhận tiếp nhận. Vui lòng kiểm tra khả năng hỗ trợ thực tế.",
        )
    return {"reminders": count, "schedules_checked": len(schedules)}
