import io
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest
import pytest_asyncio
from PIL import Image

from app.core.database import AsyncSessionLocal
from app.models.commerce import Order
from app.models.user import User
from app.modules.customer.auth_service import issue_session

pytestmark = pytest.mark.skipif(not os.environ.get("PETHOME_V2_TEST_DATABASE"), reason="requires disposable test DB")


@pytest_asyncio.fixture(autouse=True)
async def close_database_pool():
    yield
    from app.core.database import engine
    await engine.dispose()


async def login(permissions):
    async with AsyncSessionLocal() as db:
        user = User(full_name="Shop Finance QA", role="warehouse_staff", staff_permissions=permissions)
        db.add(user)
        await db.flush()
        token = await issue_session(db, user)
        await db.commit()
        return user.id, {"Authorization": "Bearer " + token["access_token"]}


@pytest.mark.asyncio
async def test_expense_receipt_audit_and_overview():
    from app.main import app
    _, manager = await login(["platform_manage"])
    _, warehouse = await login(["warehouse"])
    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=manager) as client:
        overview = await client.get("/api/v1/admin/reports/overview")
        assert overview.status_code == 200 and len(overview.json()["daily"]) == 7, overview.text
        created = await client.post("/api/v1/admin/shop-expenses", json={"spent_on":today,"category":"supplies","amount":12000,"note":"Mua túi đóng gói","reference":"QA"})
        assert created.status_code == 201, created.text
        expense_id = created.json()["id"]
        img = io.BytesIO()
        Image.new("RGB", (16,16), "white").save(img, format="PNG")
        uploaded = await client.post(f"/api/v1/admin/shop-expenses/{expense_id}/receipts", files={"file":("bill.png",img.getvalue(),"image/png")})
        assert uploaded.status_code == 201, uploaded.text
        receipt_id = uploaded.json()["id"]
        assert (await client.get(f"/api/v1/admin/shop-expenses/{expense_id}/receipts/{receipt_id}")).status_code == 200
        assert (await client.get("/api/v1/admin/reports/overview")).json()["daily"][-1]["other_expenses"] == 12000
        assert (await client.post(f"/api/v1/admin/shop-expenses/{expense_id}/void",json={"reason":"Ghi nhầm chứng từ"})).status_code == 200
        assert (await client.get("/api/v1/admin/reports/overview")).json()["daily"][-1]["other_expenses"] == 0
        listed = (await client.get("/api/v1/admin/shop-expenses")).json()
        assert listed[0]["void_reason"] == "Ghi nhầm chứng từ" and len(listed[0]["receipts"]) == 1
        assert listed[0]["actor_name"] == "Shop Finance QA"
        assert (await client.get(f"/api/v1/admin/shop-expenses/{expense_id}/receipts/{receipt_id}")).status_code == 200
        assert (await client.post("/api/v1/admin/shop-expenses",json={"spent_on":today,"category":"other","amount":100,"note":"x"},headers=warehouse)).status_code == 403


@pytest.mark.asyncio
async def test_manual_delivery_never_marks_cod_paid():
    from app.main import app
    user_id, warehouse = await login(["warehouse"])
    async with AsyncSessionLocal() as db:
        order = Order(order_code=uuid.uuid4().hex[:10].upper(), idempotency_key=uuid.uuid4().hex,
                      user_id=user_id, customer_name="QA", customer_phone="0901234567", shipping_address={},
                      status="shipped", payment_method="cod", payment_status="unpaid", subtotal_amount=50000,
                      total_amount=50000, shipping_fee=0, discount_amount=0)
        db.add(order)
        await db.commit()
        order_id = order.id
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test",headers=warehouse) as client:
        done = await client.post(f"/api/v1/admin/orders/{order_id}/delivered",json={"note":"Đã kiểm tra mã vận đơn với hãng"})
        assert done.status_code == 200 and done.json()["status"] == "delivered", done.text
        assert done.json()["payment_status"] == "unpaid"
        assert (await client.post(f"/api/v1/admin/orders/{order_id}/delivered",json={"note":"Đã kiểm tra mã vận đơn với hãng"})).status_code == 409
