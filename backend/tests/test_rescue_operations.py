"""Shelter acceptance tests using a disposable PostgreSQL database."""

import asyncio
import os
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from test_community import published, sessions, user

from app.core.database import get_db
from app.core.security import create_access_token
from app.models.rescue import (
    RescueAnimal,
    RescueEpisode,
    RescueFund,
    RescueLocation,
    RescueTask,
)
from app.models.user import User
from app.modules.rescue import router as routes
from app.modules.rescue import schemas as s
from app.modules.rescue import service as svc

pytestmark = pytest.mark.skipif(
    not os.environ.get("COMMUNITY_TEST_DATABASE"), reason="isolated database required"
)


async def staff(factory, permissions):
    async with factory() as db:
        u = User(
            full_name="Shelter QA", role="cskh_staff", staff_permissions=permissions, is_active=True
        )
        db.add(u)
        await db.commit()
        return u


async def setup(factory, person, capacity=2):
    async with factory() as db:
        loc = RescueLocation(
            name="Nhà tạm QA",
            kind="foster",
            species="cat",
            capacity=capacity,
            private_contact="PRIVATE FOSTER ADDRESS",
        )
        db.add(loc)
        await db.flush()
        a = await svc.create_animal(
            db, person, s.AnimalIn(name="Miu", species="cat", story="Câu chuyện đã xác minh")
        )
        await db.commit()
        return UUID(a["id"]), loc.id


def intake_body(a, location_id, u):
    return s.IntakeIn(
        animal_id=a,
        location_id=location_id,
        assignee_id=u,
        started_at=svc.now(),
        source_note="Đã kiểm tra bàn giao thực tế",
    )


@pytest.mark.asyncio
async def test_capacity_last_place_concurrent():
    factory = sessions()
    operator = await staff(factory, ["rescue_manage"])
    a, location_id = await setup(factory, operator, 1)
    async with factory() as db:
        second = await svc.create_animal(db, operator, s.AnimalIn(name="Miu 2", species="cat"))
        await db.commit()

    async def receive(ident):
        async with factory() as db:
            try:
                await svc.intake(db, operator, intake_body(ident, location_id, operator.id))
                await db.commit()
                return 201
            except HTTPException as exc:
                await db.rollback()
                return exc.status_code

    assert sorted(await asyncio.gather(receive(a), receive(UUID(second["id"])))) == [201, 409]
    async with factory() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(RescueEpisode)
                .where(RescueEpisode.location_id == location_id, RescueEpisode.ended_at.is_(None))
            )
            == 1
        )


@pytest.mark.asyncio
async def test_same_animal_returns_with_same_identity_and_foster_not_adoption():
    factory = sessions()
    operator = await staff(factory, ["rescue_manage"])
    a, location_id = await setup(factory, operator)
    async with factory() as db:
        await svc.intake(db, operator, intake_body(a, location_id, operator.id))
        await db.commit()
        with pytest.raises(HTTPException):
            await svc.intake(db, operator, intake_body(a, location_id, operator.id))
        await db.rollback()
        other = RescueLocation(
            name="Trạm QA",
            kind="shelter",
            species="both",
            capacity=2,
            private_contact="PRIVATE CONTACT",
        )
        db.add(other)
        await db.commit()
        animal = await svc.animal(db, a)
        await svc.transfer(
            db,
            operator,
            animal,
            s.TransferIn(
                location_id=other.id,
                assignee_id=operator.id,
                reason="Đã bàn giao từ nhà tạm về trạm",
                handed_over=True,
            ),
        )
        await db.commit()
        assert (await db.get(RescueAnimal, a)).adoption_state != "handed_over"
        await svc.close_episode(
            db, operator, await svc.animal(db, a), "returned_owner", "Đã xác minh chủ và bàn giao"
        )
        await db.commit()
        await svc.intake(db, operator, intake_body(a, location_id, operator.id))
        await db.commit()
        assert (
            await db.scalar(
                select(func.count()).select_from(RescueEpisode).where(RescueEpisode.animal_id == a)
            )
            == 2
        )
        assert (
            await db.scalar(
                select(func.count()).select_from(RescueAnimal).where(RescueAnimal.id == a)
            )
            == 1
        )


@pytest.mark.asyncio
async def test_publication_snapshot_and_assigned_care_scope():
    factory = sessions()
    operator = await staff(factory, ["rescue_manage"])
    care = await staff(factory, ["rescue_care"])
    other = await staff(factory, ["rescue_care"])
    a, location_id = await setup(factory, operator)
    async with factory() as db:
        await svc.intake(db, operator, intake_body(a, location_id, care.id))
        await db.commit()
        animal = await svc.animal(db, a)
        await svc.publish_action(
            db,
            operator,
            animal,
            s.AnimalAction(
                version=animal.version, action="publish", reason="Đã rà soát thông tin công khai"
            ),
        )
        await db.commit()
        animal.story = "PRIVATE UNAPPROVED DRAFT"
        await db.commit()
        result = svc.public_animal(animal)
        assert result["story"] == "Câu chuyện đã xác minh"
        assert (
            not {"ownership_hold", "post_id", "version", "private_contact", "assignee_id"}
            & result.keys()
        )
        assert await svc.animal(db, a, care, lock=False)
        with pytest.raises(HTTPException):
            await svc.animal(db, a, other, lock=False)


@pytest.mark.asyncio
async def test_ownership_hold_blocks_adoption_and_handover_creates_followups():
    from app.modules.community import schemas as cs
    from app.modules.community import service as community

    factory = sessions()
    operator = await staff(factory, ["rescue_manage"])
    applicant = await user(factory)
    post = await published(factory, operator)
    async with factory() as db:
        loc = RescueLocation(
            name="Trạm bàn giao",
            kind="shelter",
            species="both",
            capacity=1,
            private_contact="PRIVATE",
        )
        db.add(loc)
        await db.flush()
        created = await svc.create_animal(
            db, operator, s.AnimalIn(name="Bé bàn giao", species="cat", post_id=post.id)
        )
        aid = UUID(created["id"])
        await svc.intake(db, operator, intake_body(aid, loc.id, operator.id))
        await db.commit()
        a = await svc.animal(db, aid)
        await svc.publish_action(
            db,
            operator,
            a,
            s.AnimalAction(
                action="open", version=a.version, reason="Đã rà soát quyền bàn giao và chăm sóc"
            ),
        )
        await db.commit()
        data = cs.AdoptionCreateIn(
            consent=True,
            applicant_name="Gia đình QA",
            applicant_phone="0900000000",
            applicant_address="Địa chỉ riêng QA",
            living_condition="Gia đình có điều kiện chăm sóc phù hợp",
        )
        request = await community.create_adoption_request(
            db, post.id, applicant.id, data, uuid4().hex
        )
        request_id = request.id
        await community.adoption_action(
            db, request_id, operator.id, cs.AdoptionActionIn(action="contact")
        )
        await db.commit()
        a = await svc.animal(db, aid)
        await svc.publish_action(
            db,
            operator,
            a,
            s.AnimalAction(
                action="hold", version=a.version, reason="Có người yêu cầu xác minh chủ"
            ),
        )
        await db.commit()
        with pytest.raises(HTTPException):
            await community.adoption_action(
                db, request_id, operator.id, cs.AdoptionActionIn(action="approve")
            )
        await db.rollback()
        for action in ("release_hold", "open"):
            a = await svc.animal(db, aid)
            await svc.publish_action(
                db,
                operator,
                a,
                s.AnimalAction(
                    action=action, version=a.version, reason="Đã hoàn tất kiểm tra thông tin"
                ),
            )
            await db.commit()
        from app.modules.rescue import workflow_schemas as workflow
        from app.modules.rescue import workflow_service as ws

        request = await db.get(
            __import__("app.models.community", fromlist=["AdoptionRequest"]).AdoptionRequest,
            request_id,
        )
        await ws.check_application(
            db,
            request,
            operator,
            workflow.CheckIn(
                action="verify", note="Đã gọi xác minh liên hệ thực tế", confirmed=True
            ),
        )
        await ws.check_application(
            db,
            request,
            operator,
            workflow.CheckIn(
                action="agreement",
                note="Đã trao đổi và thống nhất điều kiện bàn giao",
                confirmed=True,
            ),
        )
        await community.adoption_action(
            db, request_id, operator.id, cs.AdoptionActionIn(action="approve")
        )
        await db.commit()
        await ws.check_application(
            db,
            request,
            operator,
            workflow.CheckIn(
                action="handover",
                note="Gia đình đã đồng ý biên bản và nhận bé thực tế",
                confirmed=True,
            ),
        )
        await community.adoption_action(
            db, request_id, operator.id, cs.AdoptionActionIn(action="complete")
        )
        await db.commit()
        await community.adoption_action(
            db, request_id, operator.id, cs.AdoptionActionIn(action="complete")
        )
        await db.commit()
        assert (await db.get(RescueAnimal, aid)).adoption_state == "handed_over"
        assert not await svc.open_episode(db, aid)
        tasks = (await db.scalars(select(RescueTask).where(RescueTask.animal_id == aid))).all()
        assert len(tasks) == 3


@pytest.mark.asyncio
async def test_manual_fund_ledger_balances_and_two_person_approval():
    factory = sessions()
    one = await staff(factory, ["rescue_finance"])
    two = await staff(factory, ["rescue_finance"])
    async with factory() as db:
        fund = RescueFund(
            title="Quỹ kiểm thử",
            purpose="Chăm sóc các bé tại trạm",
            surplus_policy="Giữ đúng mục đích đã công bố",
        )
        db.add(fund)
        await db.commit()
        fund_id = fund.id
        received = await svc.ledger(
            db,
            one,
            fund_id,
            s.LedgerIn(
                kind="received",
                amount=1000000,
                reference=uuid4().hex,
                note="Đã kiểm tra giao dịch nhận thực tế",
                anonymous=True,
                donor_name="PRIVATE DONOR",
            ),
        )
        await db.commit()
        assert (await svc.balances(db, fund_id))["available"] == 0
        await svc.ledger(
            db,
            one,
            fund_id,
            s.LedgerIn(
                kind="settled",
                amount=1000000,
                reference=uuid4().hex,
                note="Đã đối soát tiền về quỹ",
                reverses_id=received["id"],
            ),
        )
        await db.commit()
        e = await routes.expense(
            s.ExpenseIn(fund_id=fund_id, amount=400000, purpose="Mua vật tư đúng mục đích quỹ"),
            uuid4().hex,
            one,
            db,
        )
        await db.commit()
        with pytest.raises(HTTPException):
            await routes.expense_action(UUID(e["id"]), s.ExpenseAction(action="approve"), one, db)
        await db.rollback()
        await routes.expense_action(UUID(e["id"]), s.ExpenseAction(action="approve"), two, db)
        await db.commit()
        assert (await svc.balances(db, fund_id))["available"] == 600000
        with pytest.raises(HTTPException):
            await svc.ledger(
                db,
                one,
                fund_id,
                s.LedgerIn(
                    kind="refund",
                    amount=700000,
                    reference=uuid4().hex,
                    note="Kiểm tra không vượt ngân sách đã giữ",
                    reverses_id=received["id"],
                ),
            )
        await db.rollback()
        ref = uuid4().hex
        await routes.expense_action(
            UUID(e["id"]), s.ExpenseAction(action="pay", reference=ref), two, db
        )
        await db.commit()
        await routes.expense_action(
            UUID(e["id"]), s.ExpenseAction(action="pay", reference=ref), two, db
        )
        await db.commit()
        balance = await svc.balances(db, fund_id)
        assert balance["spent"] == 400000 and balance["available"] == 600000


@pytest.mark.asyncio
async def test_report_idempotency_private_scope_and_shop_staff_separation(monkeypatch):
    from app.main import app

    factory = sessions()
    shop = await staff(factory, ["customer_support"])
    rescuer = await staff(factory, ["rescue_manage"])
    financier = await staff(factory, ["rescue_finance"])
    monkeypatch.setattr(routes, "enforce_rate_limit", AsyncMock())

    async def database():
        async with factory() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    app.dependency_overrides[get_db] = database

    def auth(u):
        return {"Authorization": "Bearer " + create_access_token(subject=str(u.id), role=u.role)}

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            assert (await c.get("/api/v1/rescue/config")).status_code == 200
            body = {
                "description": "Có một bé cần trạm kiểm tra giúp",
                "species": "cat",
                "count_estimate": 1,
                "seen_at": svc.now().isoformat(),
                "private_location": "PRIVATE EXACT ADDRESS",
                "private_contact": "0900000000",
                "consent": True,
            }
            headers = {"Idempotency-Key": uuid4().hex, "X-CSRF-Token": c.cookies.get("csrf_token")}
            first = await c.post("/api/v1/rescue/reports", json=body, headers=headers)
            assert first.status_code == 201, first.text
            again = await c.post("/api/v1/rescue/reports", json=body, headers=headers)
            assert first.json()["id"] == again.json()["id"]
            assert (
                await c.post(
                    "/api/v1/rescue/reports",
                    json={**body, "description": "Nội dung đã bị thay đổi khác trước"},
                    headers=headers,
                )
            ).status_code == 409
            assert len((await c.get("/api/v1/rescue/me/reports")).json()) == 1
            c.cookies.clear()
            assert (await c.get("/api/v1/rescue/me/reports")).json() == []
            assert (
                await c.get("/api/v1/admin/rescue/workspace", headers=auth(shop))
            ).status_code == 403
            assert (
                await c.get("/api/v1/admin/community/posts", headers=auth(shop))
            ).status_code == 403
            assert (await c.get("/api/v1/admin/orders", headers=auth(rescuer))).status_code == 403
            assert (
                await c.get("/api/v1/admin/rescue/workspace", headers=auth(financier))
            ).status_code == 403
            assert (
                await c.get("/api/v1/admin/rescue/finance", headers=auth(rescuer))
            ).status_code == 403
            data = (await c.get("/api/v1/admin/rescue/workspace", headers=auth(rescuer))).json()
            assert any(r["id"] == first.json()["id"] for r in data["reports"])
            assert (await c.get("/api/v1/rescue/transparency")).json() == []
            assert (await c.post("/api/v1/rescue/donation-intents", json={})).status_code == 503
    finally:
        app.dependency_overrides.pop(get_db, None)
