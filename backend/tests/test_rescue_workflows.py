"""Exercise new workflows on disposable PostgreSQL; no production data or external providers."""

import asyncio
import hashlib
import hmac
import io
import os
from datetime import timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import func, select
from test_community import sessions, user
from test_rescue_operations import intake_body, setup, staff

from app.core.database import get_db
from app.core.security import create_access_token
from app.models.rescue import RescueFund, RescueSupply
from app.models.rescue_workflow import (
    RescueAppointment,
    RescueCampaign,
    RescueDonationIntent,
    RescuePartner,
    RescueReminder,
    RescueSupplyMovement,
)
from app.modules.rescue import contributions as funds
from app.modules.rescue import service as svc
from app.modules.rescue import workflow_router as routes
from app.modules.rescue import workflow_schemas as s
from app.modules.rescue import workflow_service as ws

pytestmark = pytest.mark.skipif(
    not os.environ.get("COMMUNITY_TEST_DATABASE"), reason="isolated database required"
)


def client_for(factory, person):
    from app.main import app

    async def override():
        async with factory() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    app.dependency_overrides[get_db] = override
    token = create_access_token(subject=str(person.id), role=person.role)
    return app, httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer " + token},
    )


@pytest.mark.asyncio
async def test_appointment_race_cancel_reschedule_reminders_replay():
    factory = sessions()
    operator = await staff(factory, ["rescue_manage"])
    applicant = await user(factory)
    aid, _ = await setup(factory, operator)
    start = svc.now() + timedelta(hours=2)
    body = s.AppointmentIn(
        animal_id=aid,
        organizer_id=operator.id,
        participant_id=applicant.id,
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        kind="visit",
        location="Địa điểm riêng chỉ người tham gia được biết",
    )

    async def create():
        async with factory() as db:
            try:
                result = await ws.create_appointment(db, operator, body)
                await db.commit()
                return (201, result)
            except HTTPException as exc:
                await db.rollback()
                return (exc.status_code, None)

    results = await asyncio.gather(create(), create())
    assert sorted(r[0] for r in results) == [201, 409]
    ident = UUID(next(r[1]["id"] for r in results if r[0] == 201))
    async with factory() as db:
        row = await ws.appointment_action(
            db,
            applicant,
            ident,
            s.AppointmentAction(
                version=1, action="confirm", reason="Gia đình đã xác nhận tham gia"
            ),
        )
        await db.commit()
        await ws.appointment_action(
            db,
            operator,
            ident,
            s.AppointmentAction(
                version=row["version"],
                action="reschedule",
                starts_at=start + timedelta(days=2),
                ends_at=start + timedelta(days=2, hours=1),
                reason="Đổi giờ theo đề nghị gia đình",
            ),
        )
        await db.commit()
        await ws.maintenance(db)
        await db.commit()
        assert not await db.scalar(
            select(RescueReminder.id).where(RescueReminder.resource_id == ident)
        )
        row = await db.get(RescueAppointment, ident)
        await ws.appointment_action(
            db,
            applicant,
            ident,
            s.AppointmentAction(
                version=row.version, action="cancel", reason="Gia đình xin hủy lịch hẹn này"
            ),
        )
        await db.commit()
        await ws.maintenance(db)
        await db.commit()
        assert not await db.scalar(
            select(RescueReminder.id).where(RescueReminder.resource_id == ident)
        )
    app, client = client_for(factory, await user(factory))
    try:
        async with client:
            result = await client.post(
                f"/api/v1/rescue/appointments/{ident}/action",
                json={
                    "version": 4,
                    "action": "confirm",
                    "reason": "Trying someone else appointment",
                },
            )
            assert result.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_foster_approval_creates_capacity_without_role_grant():
    factory = sessions()
    operator = await staff(factory, ["rescue_manage"])
    applicant = await user(factory)
    async with factory() as db:
        p = RescuePartner(
            user_id=applicant.id,
            kind="foster",
            name="Nhà tạm QA",
            contact="PRIVATE CONTACT",
            area="Hà Nội",
            conditions="Có phòng riêng và phương án dự phòng",
            species="cat",
            capacity=1,
            available_from=svc.now() - timedelta(days=1),
            available_until=svc.now() + timedelta(days=30),
        )
        db.add(p)
        await db.commit()
        ident = p.id
        result = await ws.partner_action(
            db,
            operator,
            ident,
            s.DecisionIn(version=1, action="approve", reason="Đã kiểm tra điều kiện thực tế"),
        )
        await db.commit()
        assert result["location_id"]
        from app.models.user import User

        saved_applicant = await db.get(User, applicant.id)
        assert saved_applicant.role == "customer" and not saved_applicant.staff_permissions
        animal = await svc.create_animal(
            db,
            operator,
            __import__("app.modules.rescue.schemas", fromlist=["AnimalIn"]).AnimalIn(
                name="Bé nhà tạm", species="cat"
            ),
        )
        await svc.intake(
            db, operator, intake_body(UUID(animal["id"]), UUID(result["location_id"]), operator.id)
        )
        await db.commit()
        with pytest.raises(HTTPException):
            await ws.partner_action(
                db,
                applicant,
                ident,
                s.DecisionIn(version=2, action="withdraw", reason="Xin kết thúc chăm sóc tạm"),
            )
        await db.rollback()


@pytest.mark.asyncio
async def test_supply_concurrent_use_and_quarantine_release():
    factory = sessions()
    operator = await staff(factory, ["rescue_manage"])
    async with factory() as db:
        r = RescueSupply(
            name="Thức ăn thử nghiệm",
            quantity=5,
            accepted_quantity=5,
            unit="túi",
            reference=uuid4().hex,
            note="Đã kiểm tra hàng thực tế",
            actor_id=operator.id,
        )
        db.add(r)
        await db.commit()
        ident = r.id

    async def use():
        async with factory() as db:
            try:
                await ws.move_supply(
                    db,
                    operator,
                    ident,
                    s.SupplyMovementIn(
                        kind="use",
                        quantity=4,
                        reason="Đã dùng cho các bé ở trạm",
                        reference=uuid4().hex,
                    ),
                )
                await db.commit()
                return 201
            except HTTPException as exc:
                await db.rollback()
                return exc.status_code

    assert sorted(await asyncio.gather(use(), use())) == [201, 409]
    async with factory() as db:
        await ws.move_supply(
            db,
            operator,
            ident,
            s.SupplyMovementIn(
                kind="quarantine",
                quantity=1,
                reason="Kiểm tra dấu hiệu bao bì bị hở",
                reference=uuid4().hex,
            ),
        )
        await db.commit()
        stock = await ws.supply_stock(db, await db.get(RescueSupply, ident))
        assert stock["usable"] == 0 and stock["quarantined"] == 1
        await ws.move_supply(
            db,
            operator,
            ident,
            s.SupplyMovementIn(
                kind="release",
                quantity=1,
                reason="Đã kiểm tra lại và đủ điều kiện",
                reference=uuid4().hex,
            ),
        )
        await db.commit()
        assert (await ws.supply_stock(db, await db.get(RescueSupply, ident)))["usable"] == 1
        assert (
            await db.scalar(
                select(func.count())
                .select_from(RescueSupplyMovement)
                .where(RescueSupplyMovement.receipt_id == ident)
            )
            == 3
        )


@pytest.mark.asyncio
async def test_money_manual_then_callback_late_mismatch_and_refund(monkeypatch):
    factory = sessions()
    one = await staff(factory, ["rescue_finance"])
    two = await staff(factory, ["rescue_finance"])
    donor = await user(factory)
    async with factory() as db:
        fund = RescueFund(
            title="Quỹ chăm sóc QA",
            purpose="Dành riêng cho chăm sóc tại trạm",
            surplus_policy="Khoản dư giữ đúng mục đích, xem xét hoàn theo yêu cầu",
        )
        db.add(fund)
        await db.flush()
        campaign = RescueCampaign(
            fund_id=fund.id,
            target=100000,
            opens_at=svc.now() - timedelta(days=2),
            closes_at=svc.now() - timedelta(days=1),
            status="closed",
        )
        db.add(campaign)
        await db.flush()
        intent = RescueDonationIntent(
            campaign_id=campaign.id,
            user_id=donor.id,
            code="UH-" + uuid4().hex[:10],
            amount=100000,
            anonymous=True,
            expires_at=svc.now() - timedelta(days=1),
            purpose_snapshot={"merchant": "rescue-only", "surplus_policy": fund.surplus_policy},
        )
        db.add(intent)
        await db.commit()
        fund_id, intent_id, code = fund.id, intent.id, intent.code
        proof = uuid4().hex
        from app.modules.rescue.schemas import LedgerIn

        received = await svc.ledger(
            db,
            one,
            fund_id,
            LedgerIn(
                kind="received",
                amount=100000,
                reference=proof,
                note="Đã kiểm tra tiền đến trong ngân hàng",
            ),
        )
        await db.commit()
        wrong = await funds.reconcile(
            db,
            one,
            s.DonationConfirm(
                code=code,
                amount=99999,
                reference=uuid4().hex,
                merchant="rescue-only",
                note="Kiểm thử tiền không khớp khoản hỗ trợ",
            ),
        )
        assert wrong["status"] == "amount_mismatch"
        await db.commit()
        body = s.DonationConfirm(
            code=code,
            amount=100000,
            reference=proof,
            merchant="rescue-only",
            note="Đã kiểm tra tiền đến trong ngân hàng",
        )
        first = await funds.reconcile(db, one, body)
        await db.commit()
        assert first["status"] == "surplus_review"
        assert await funds.reconcile(db, one, body) == first
        await db.commit()
        assert (await svc.balances(db, fund_id))["confirmed"] == 100000
        assert (await svc.balances(db, fund_id))["settled"] == 100000
        assert (await db.get(RescueDonationIntent, intent_id)).status == "needs_review"
        proposal = await funds.refund(
            s.RefundIn(
                entry_id=UUID(received["id"]),
                amount=60000,
                reason="Hoàn theo yêu cầu người gửi đúng chính sách",
            ),
            uuid4().hex,
            one,
            db,
        )
        rid = UUID(proposal["id"])
        await db.commit()
        with pytest.raises(HTTPException):
            await funds.refund_action(
                rid, s.RefundAction(action="approve", confirmed=True), one, db
            )
        await db.rollback()
        await funds.refund_action(rid, s.RefundAction(action="approve", confirmed=True), two, db)
        await db.commit()
        assert (await svc.balances(db, fund_id))["available"] == 40000
        paid = s.RefundAction(action="confirm_paid", reference=uuid4().hex, confirmed=True)
        await funds.refund_action(rid, paid, one, db)
        await db.commit()
        await funds.refund_action(rid, paid, one, db)
        await db.commit()
        assert (await svc.balances(db, fund_id))["refunded"] == 60000
        extra = s.DonationConfirm(
            code=code,
            amount=25000,
            reference=uuid4().hex,
            merchant="rescue-only",
            note="Khoản chuyển thêm cần kiểm tra số thực nhận",
        )
        mismatch = await funds.reconcile(db, one, extra)
        await db.commit()
        assert mismatch["status"] == "amount_mismatch"
        reviewed = await funds.review_exception(
            UUID(mismatch["id"]),
            s.DonationReviewIn(**extra.model_dump(), decision="record"),
            one,
            db,
        )
        await db.commit()
        assert reviewed["status"] == "surplus_review_resolved"
        assert (await svc.balances(db, fund_id))["settled"] == 125000
        await funds.reconcile(db, one, extra)
        await db.commit()
        assert (await svc.balances(db, fund_id))["settled"] == 125000

    # A correctly signed delivery after manual reconciliation reuses the same receipt,
    # even if the provider adds a different note and new intents are disabled.
    import json

    from app.core.config import get_settings

    await user(factory, "owner")
    secret = "test-only-rescue-secret-" + ("0" * 32)
    monkeypatch.setattr(get_settings(), "rescue_webhook_secret", secret)
    payload = body.model_dump()
    payload["note"] = "Thông báo bổ sung từ hệ thống đối soát thử nghiệm"
    raw = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    app, client = client_for(factory, donor)
    try:
        async with client:
            response = await client.post(
                "/api/v1/webhooks/rescue/transfers",
                content=raw,
                headers={"Content-Type": "application/json", "X-Rescue-Signature": signature},
            )
            assert response.status_code == 200, response.text
            assert response.json()["id"] == first["id"]
            assert (
                await client.post(
                    "/api/v1/webhooks/rescue/transfers",
                    content=raw,
                    headers={"X-Rescue-Signature": "invalid"},
                )
            ).status_code == 403
        async with factory() as db:
            assert (await svc.balances(db, fund_id))["settled"] == 125000
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_private_evidence_auth_and_publication(monkeypatch, tmp_path):
    from app.core.config import get_settings
    from app.models.rescue_workflow import RescueAsset

    factory = sessions()
    operator = await staff(factory, ["rescue_manage"])
    outsider = await staff(factory, ["customer_support"])
    aid, _ = await setup(factory, operator)
    monkeypatch.setattr(get_settings(), "community_upload_dir", str(tmp_path))
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "green").save(buffer, format="JPEG")
    app, client = client_for(factory, operator)
    try:
        async with client:
            response = await client.post(
                "/api/v1/rescue/files",
                data={
                    "resource_kind": "animal",
                    "resource_id": str(aid),
                    "caption": "Bản chụp chỉ nội bộ",
                },
                files={"file": ("image.jpg", buffer.getvalue(), "image/jpeg")},
            )
            assert response.status_code == 201, response.text
            ident = response.json()["id"]
            listing = await client.get(
                "/api/v1/rescue/files", params={"resource_kind": "animal", "resource_id": str(aid)}
            )
            assert listing.status_code == 200
            private_url = listing.json()[0]["url"].replace("/api/proxy", "")
            assert (await client.get(private_url)).status_code == 200
            assert (await client.get(f"/api/v1/rescue/public-images/{ident}")).status_code == 404
            outsider_token = create_access_token(subject=str(outsider.id), role=outsider.role)
            blocked = await client.get(
                private_url, headers={"Authorization": "Bearer " + outsider_token}
            )
            assert blocked.status_code == 403
            assert (await client.delete(f"/api/v1/rescue/files/{ident}")).status_code == 200
            assert (await client.get(private_url)).status_code == 404
            medical = await client.post(
                "/api/v1/rescue/files",
                data={
                    "resource_kind": "care",
                    "resource_id": str(aid),
                    "caption": "Bản chụp giấy khám riêng tư",
                },
                files={"file": ("medical.jpg", buffer.getvalue(), "image/jpeg")},
            )
            assert medical.status_code == 201, medical.text
            medical_id = medical.json()["id"]
            assert (
                await client.post(
                    f"/api/v1/admin/rescue/files/{medical_id}/publish?rights_confirmed=true"
                )
            ).status_code == 422
            assert (
                await client.get(f"/api/v1/rescue/public-images/{medical_id}")
            ).status_code == 404
        async with factory() as db:
            assert (await db.get(RescueAsset, UUID(ident))).deleted_at
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_unsigned_callback_and_portal_permission_boundaries():
    factory = sessions()
    shop = await staff(factory, ["customer_support"])
    app, client = client_for(factory, shop)
    try:
        async with client:
            assert (await client.get("/api/v1/rescue/me/workspace")).status_code == 200
            for path in ("coordination", "supply-stock", "contributions"):
                assert (await client.get("/api/v1/admin/rescue/" + path)).status_code == 403
            assert (
                await client.post("/api/v1/webhooks/rescue/transfers", json={})
            ).status_code == 403
            result = await client.get("/api/v1/rescue/campaigns")
            assert result.status_code == 200 and result.json()["enabled"] is False
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_two_staff_approve_two_applicants_concurrently_over_http():
    from test_community import published

    from app.models.community import AdoptionRequest
    from app.models.rescue_workflow import RescueApplicationCheck
    from app.modules.community import schemas as cs
    from app.modules.community import service as community
    from app.modules.rescue.schemas import AnimalAction, AnimalIn

    factory = sessions()
    first = await staff(factory, ["rescue_manage"])
    second = await staff(factory, ["rescue_manage"])
    applicants = [await user(factory), await user(factory)]
    post = await published(factory, first)
    _, location = await setup(factory, first)
    async with factory() as db:
        a = await svc.create_animal(
            db, first, AnimalIn(name="Bé ghép đồng thời", species="cat", post_id=post.id)
        )
        aid = UUID(a["id"])
        await svc.intake(db, first, intake_body(aid, location, first.id))
        animal = await svc.animal(db, aid)
        await svc.publish_action(
            db,
            first,
            animal,
            AnimalAction(
                version=animal.version, action="open", reason="Đã kiểm tra điều kiện bàn giao"
            ),
        )
        await db.commit()
        request_ids = []
        for applicant in applicants:
            request = await community.create_adoption_request(
                db,
                post.id,
                applicant.id,
                cs.AdoptionCreateIn(
                    consent=True,
                    applicant_name="Gia đình thử nghiệm",
                    applicant_phone="0900000000",
                    applicant_address="Địa chỉ riêng của gia đình",
                    living_condition="Có điều kiện chăm sóc và đã trao đổi với trạm",
                ),
                uuid4().hex,
            )
            request_ids.append(request.id)
            await community.adoption_action(
                db, request.id, first.id, cs.AdoptionActionIn(action="contact")
            )
            db.add(
                RescueApplicationCheck(
                    application_id=request.id,
                    verified_by=first.id,
                    verified_at=svc.now(),
                    contact_method="phone",
                    verification_note="Đã kiểm tra thực tế",
                )
            )
        await db.commit()
    app, client = client_for(factory, first)
    try:
        async with client:

            async def approve(ident, person):
                token = create_access_token(subject=str(person.id), role=person.role)
                return await client.post(
                    f"/api/v1/admin/community/adoption-requests/{ident}/action",
                    json={"action": "approve"},
                    headers={"Authorization": "Bearer " + token},
                )

            responses = await asyncio.gather(
                approve(request_ids[0], first), approve(request_ids[1], second)
            )
            assert sorted(r.status_code for r in responses) == [200, 409]
        async with factory() as db:
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(AdoptionRequest)
                    .where(AdoptionRequest.post_id == post.id, AdoptionRequest.status == "approved")
                )
                == 1
            )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_private_chat_participant_scope_and_idempotency():
    from app.models.rescue_workflow import RescueMessage

    factory = sessions()
    applicant = await user(factory)
    outsider = await user(factory)
    app, client = client_for(factory, applicant)
    try:
        async with client:
            body = {
                "resource_kind": "support",
                "resource_id": str(applicant.id),
                "body": "Trao đổi riêng về việc hỗ trợ chăm sóc tại Hà Nội",
            }
            headers = {"Idempotency-Key": uuid4().hex}
            first = await client.post("/api/v1/rescue/messages", json=body, headers=headers)
            again = await client.post("/api/v1/rescue/messages", json=body, headers=headers)
            assert first.status_code == 201 and first.json()["id"] == again.json()["id"]
            response = await client.get(
                "/api/v1/rescue/messages",
                params={"resource_kind": "support", "resource_id": str(applicant.id)},
            )
            assert response.status_code == 200 and response.json()[0]["body"] == body["body"]
            token = create_access_token(subject=str(outsider.id), role=outsider.role)
            assert (
                await client.get(
                    "/api/v1/rescue/messages",
                    params={"resource_kind": "support", "resource_id": str(applicant.id)},
                    headers={"Authorization": "Bearer " + token},
                )
            ).status_code == 404
        async with factory() as db:
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(RescueMessage)
                    .where(RescueMessage.resource_id == applicant.id)
                )
                == 1
            )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_worker_rollback_replay_and_care_stop_on_transfer():
    from app.models.rescue import RescueLocation, RescueTask
    from app.models.rescue_workflow import RescueCareSchedule
    from app.modules.rescue.schemas import TransferIn

    factory = sessions()
    operator = await staff(factory, ["rescue_manage"])
    other = await staff(factory, ["rescue_care"])
    aid, location = await setup(factory, operator)
    async with factory() as db:
        episode = await svc.intake(db, operator, intake_body(aid, location, operator.id))
        schedule = RescueCareSchedule(
            episode_id=UUID(episode["id"]),
            title="Chăm sóc lặp thử nghiệm",
            instructions="Làm theo hướng dẫn đã được xác nhận",
            interval_days=7,
            next_at=svc.now() - timedelta(hours=2),
            until_at=svc.now() + timedelta(days=21),
        )
        destination = RescueLocation(
            name="Nơi chăm sóc mới QA", kind="shelter", species="cat", capacity=2
        )
        db.add_all([schedule, destination])
        await db.commit()
        schedule_id, destination_id = schedule.id, destination.id
        await ws.maintenance(db)
        await (
            db.rollback()
        )  # Worker dies before commit: replay must recreate the same occurrence once.
        await ws.maintenance(db)
        await db.commit()
        tasks = (await db.scalars(select(RescueTask).where(RescueTask.animal_id == aid))).all()
        assert len(tasks) == 1
        task_id = tasks[0].id
        notifications = await db.scalar(
            select(func.count())
            .select_from(RescueReminder)
            .where(RescueReminder.resource_id == task_id)
        )
        await ws.maintenance(db)
        await db.commit()
        assert (
            await db.scalar(
                select(func.count())
                .select_from(RescueReminder)
                .where(RescueReminder.resource_id == task_id)
            )
            == notifications
        )
        await svc.transfer(
            db,
            operator,
            await svc.animal(db, aid),
            TransferIn(
                location_id=destination_id,
                assignee_id=other.id,
                reason="Đã bàn giao trách nhiệm cho ca khác",
                handed_over=True,
            ),
        )
        await db.commit()
        await ws.maintenance(db)
        await db.commit()
        assert (await db.get(RescueTask, task_id)).status == "skipped"
        assert not (await db.get(RescueCareSchedule, schedule_id)).active


@pytest.mark.asyncio
async def test_one_visit_slot_can_only_be_booked_once_over_http():
    from test_community import published

    from app.models.rescue_workflow import RescueVisitSlot
    from app.modules.community import schemas as cs
    from app.modules.community import service as community
    from app.modules.rescue.schemas import AnimalAction, AnimalIn

    factory = sessions()
    operator = await staff(factory, ["rescue_manage"])
    applicants = [await user(factory), await user(factory)]
    post = await published(factory, operator)
    _, location = await setup(factory, operator)
    async with factory() as db:
        a = await svc.create_animal(
            db, operator, AnimalIn(name="Bé chọn lịch QA", species="cat", post_id=post.id)
        )
        aid = UUID(a["id"])
        await svc.intake(db, operator, intake_body(aid, location, operator.id))
        for action in ("open", "publish"):
            animal = await svc.animal(db, aid)
            await svc.publish_action(
                db,
                operator,
                animal,
                AnimalAction(
                    version=animal.version,
                    action=action,
                    reason="Đã kiểm tra điều kiện công bố và bàn giao",
                ),
            )
        requests = []
        for person in applicants:
            row = await community.create_adoption_request(
                db,
                post.id,
                person.id,
                cs.AdoptionCreateIn(
                    consent=True,
                    applicant_name="Gia đình chọn lịch",
                    applicant_phone="0900000000",
                    applicant_address="Địa chỉ riêng QA",
                    living_condition="Có thời gian chăm sóc và muốn trao đổi với trạm",
                ),
                uuid4().hex,
            )
            requests.append(row.id)
        start = svc.now() + timedelta(days=2)
        slot = await routes.create_slot(
            s.VisitSlotIn(
                animal_id=aid,
                organizer_id=operator.id,
                starts_at=start,
                ends_at=start + timedelta(hours=1),
                location="Địa chỉ chỉ chia sẻ sau khi đặt lịch",
            ),
            uuid4().hex,
            operator,
            db,
        )
        await db.commit()
        slot_id = UUID(slot["id"])
    app, client = client_for(factory, applicants[0])
    try:
        async with client:

            async def book(person, application):
                token = create_access_token(subject=str(person.id), role=person.role)
                return await client.post(
                    f"/api/v1/rescue/visit-slots/{slot_id}/book",
                    json={"application_id": str(application)},
                    headers={"Authorization": "Bearer " + token, "Idempotency-Key": uuid4().hex},
                )

            results = await asyncio.gather(
                book(applicants[0], requests[0]), book(applicants[1], requests[1])
            )
            assert sorted(r.status_code for r in results) == [201, 409], [
                (r.status_code, r.text) for r in results
            ]
        async with factory() as db:
            assert (await db.get(RescueVisitSlot, slot_id)).appointment_id
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_foster_update_requires_review_and_journal_is_scoped():
    from app.models.rescue import RescueLocation
    from app.modules.rescue.schemas import CareIn

    factory = sessions()
    operator = await staff(factory, ["rescue_manage"])
    household = await user(factory)
    outsider = await user(factory)
    aid, _ = await setup(factory, operator)
    async with factory() as db:
        p = RescuePartner(
            user_id=household.id,
            kind="foster",
            name="Nhà QA",
            contact="0900000000",
            area="Hà Nội",
            conditions="Phòng riêng và đã kiểm tra điều kiện",
            species="cat",
            capacity=1,
            available_from=svc.now() - timedelta(days=1),
            available_until=svc.now() + timedelta(days=30),
        )
        db.add(p)
        await db.commit()
        pid = p.id
        approved = await ws.partner_action(
            db,
            operator,
            pid,
            s.DecisionIn(version=1, action="approve", reason="Đã kiểm tra điều kiện nhà tạm"),
        )
        await svc.intake(db, operator, intake_body(aid, UUID(approved["location_id"]), operator.id))
        await db.commit()
        rows = await routes.my_foster_animals(household, db)
        assert any(r["id"] == aid for r in rows)
        assert not await routes.my_foster_animals(outsider, db)
        await routes.foster_journal(
            aid,
            CareIn(
                kind="observation", note="Bé đã ăn và đang làm quen nhà tạm", occurred_at=svc.now()
            ),
            uuid4().hex,
            household,
            db,
        )
        await db.commit()
        update = s.PartnerUpdateIn(
            version=2,
            kind="foster",
            name="Nhà QA",
            contact="0900000000",
            area="Hà Nội",
            conditions="Điều kiện mới đề nghị kiểm tra thêm",
            species="cat",
            capacity=2,
            available_from=svc.now(),
            available_until=svc.now() + timedelta(days=45),
            consent=True,
        )
        await routes.update_partner(pid, update, household, db)
        await db.commit()
        loc = await db.get(RescueLocation, UUID(approved["location_id"]))
        assert loc.capacity == 1  # A household cannot raise its approved capacity.
        await ws.partner_action(
            db,
            operator,
            pid,
            s.DecisionIn(
                version=3, action="approve", reason="Đã kiểm tra lại năng lực và điều kiện mới"
            ),
        )
        await db.commit()
        await db.refresh(loc)
        assert loc.capacity == 2


@pytest.mark.asyncio
async def test_period_report_counts_reports_cases_animals_and_episodes_separately():
    from datetime import UTC, datetime

    from app.models.rescue import RescueAnimal, RescueCase, RescueEpisode, RescueReport

    factory = sessions()
    operator = await staff(factory, ["rescue_manage"])
    aid, location = await setup(factory, operator)
    start = datetime(2010, 1, 1, tzinfo=UTC)
    async with factory() as db:
        case = RescueCase(
            code="CASE-" + uuid4().hex[:10],
            summary="Một ca, nhiều tin và bé",
            coordinator_id=operator.id,
            created_at=start,
        )
        other = RescueAnimal(
            name="Bé cùng ca", species="cat", code=svc.code("BE-"), slug=uuid4().hex
        )
        third = RescueAnimal(
            name="Bé thứ ba cùng ca", species="cat", code=svc.code("BE-"), slug=uuid4().hex
        )
        db.add_all([case, other, third])
        await db.flush()
        db.add_all(
            [
                RescueEpisode(
                    animal_id=aid,
                    case_id=case.id,
                    location_id=location,
                    assignee_id=operator.id,
                    started_at=start,
                    ended_at=start + timedelta(days=1),
                    outcome="adopted",
                    source_note="Lượt đầu",
                ),
                RescueEpisode(
                    animal_id=aid,
                    case_id=case.id,
                    location_id=location,
                    assignee_id=operator.id,
                    started_at=start + timedelta(days=3),
                    ended_at=start + timedelta(days=5),
                    outcome="returned_owner",
                    source_note="Quay lại cùng danh tính",
                ),
                RescueEpisode(
                    animal_id=other.id,
                    case_id=case.id,
                    location_id=location,
                    assignee_id=operator.id,
                    started_at=start,
                    ended_at=start + timedelta(days=2),
                    outcome="transferred",
                    source_note="Bé thứ hai",
                ),
            ]
        )
        db.add(
            RescueEpisode(
                animal_id=third.id,
                case_id=case.id,
                location_id=location,
                assignee_id=operator.id,
                started_at=start,
                ended_at=start + timedelta(days=4),
                outcome="other",
                source_note="Bé thứ ba cùng ca",
            )
        )
        for _ in range(2):
            db.add(
                RescueReport(
                    code="REPORT-" + uuid4().hex[:10],
                    description="Nhiều người báo cùng ca cứu hộ",
                    species="cat",
                    count_estimate=2,
                    seen_at=start,
                    private_location="PRIVATE ADDRESS",
                    private_contact="PRIVATE CONTACT",
                    case_id=case.id,
                    created_at=start,
                )
            )
        await db.commit()
        report = await routes.activity_report(start, start + timedelta(days=30), operator, db)
        assert report["reports"] == 2 and report["cases"] == 1
        assert report["intake_episodes"] == 4 and report["distinct_animals"] == 3
        assert report["outcomes"] == {
            "adopted": 1,
            "returned_owner": 1,
            "transferred": 1,
            "other": 1,
        }
        assert (
            report["return_cohort_30_days"]["matured"] == 1
            and report["return_cohort_30_days"]["rate"] == 1
        )


@pytest.mark.asyncio
async def test_unpublished_profile_is_absent_from_public_api():
    from app.modules.rescue.schemas import AnimalAction

    factory = sessions()
    operator = await staff(factory, ["rescue_manage"])
    aid, _ = await setup(factory, operator)
    async with factory() as db:
        a = await svc.animal(db, aid)
        slug = a.slug
        await svc.publish_action(
            db,
            operator,
            a,
            AnimalAction(version=a.version, action="publish", reason="Nội dung đã được kiểm tra"),
        )
        await db.commit()
        a = await svc.animal(db, aid)
        await svc.publish_action(
            db,
            operator,
            a,
            AnimalAction(
                version=a.version, action="unpublish", reason="Tạm gỡ để kiểm tra quyền công bố"
            ),
        )
        await db.commit()
    app, client = client_for(factory, operator)
    try:
        async with client:
            assert (await client.get("/api/v1/rescue/animals/" + slug)).status_code == 404
            response = await client.get("/api/v1/rescue/animals")
            assert response.status_code == 200 and all(r["id"] != str(aid) for r in response.json())
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_shipment_receipt_retry_counts_only_actual_goods_once():
    from app.models.rescue_workflow import RescueSupplyNeed, RescueSupplyPledge

    factory = sessions()
    operator = await staff(factory, ["rescue_manage"])
    donor = await user(factory)
    async with factory() as db:
        need = RescueSupplyNeed(
            title="Thức ăn trạm cần",
            unit="túi",
            quantity=10,
            instructions="Trao đổi về hạn và nơi giao trước khi gửi",
        )
        db.add(need)
        await db.flush()
        pledge = RescueSupplyPledge(
            user_id=donor.id,
            need_id=need.id,
            quantity=10,
            contact="0900000000",
            status="in_transit",
            tracking_reference=uuid4().hex,
        )
        db.add(pledge)
        await db.commit()
        ident = pledge.id
        reference = uuid4().hex
        key = uuid4().hex
        body = s.PledgeAction(
            version=1,
            action="receive",
            reference=reference,
            quantity=10,
            accepted_quantity=9,
            note="Nhận thực tế mười túi, một túi chờ kiểm tra",
        )
        first = await routes.pledge_action(ident, body, key, operator, db)
        await db.commit()
        assert await routes.pledge_action(ident, body, key, operator, db) == first
        await db.commit()
        receipts = (
            await db.scalars(select(RescueSupply).where(RescueSupply.reference == reference))
        ).all()
        assert len(receipts) == 1
        stock = await ws.supply_stock(db, receipts[0])
        assert stock["usable"] == 9 and stock["quarantined"] == 1
        with pytest.raises(HTTPException):
            await routes.pledge_action(ident, body, uuid4().hex, operator, db)
        await db.rollback()
