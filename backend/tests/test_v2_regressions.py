import os
import uuid
from datetime import datetime, UTC, timedelta
import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select, func
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.commerce import Order
from app.models.inventory import StockMovement
from app.modules.customer.auth_service import issue_session

pytestmark = pytest.mark.skipif(not os.environ.get("PETHOME_V2_TEST_DATABASE"), reason="requires disposable test DB")


@pytest_asyncio.fixture(autouse=True)
async def close_database_pool():
    yield
    from app.core.database import engine
    await engine.dispose()


async def account(permissions):
    async with AsyncSessionLocal() as db:
        user = User(full_name="V2 QA", role="warehouse_staff", staff_permissions=permissions)
        db.add(user); await db.flush()
        tokens = await issue_session(db, user)
        await db.commit()
        return user.id, {"Authorization": "Bearer " + tokens["access_token"]}


@pytest.mark.asyncio
async def test_guest_cannot_add_to_cart():
    from app.main import app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/cart/items", json={"variant_id": str(uuid.uuid4()), "qty": 1})
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_qa_handoff_phone_and_support_queue():
    from app.main import app
    from app.modules.order.schemas import CheckoutRequest
    from app.modules.customer.schemas import ProfileUpdateIn
    from pydantic import ValidationError

    common = {"idempotency_key": "qa-handoff-phone", "customer_name": "QA",
              "shipping_address": {"full_address": "12 Đường Hoa, Thành phố Hồ Chí Minh"},
              "payment_method": "cod"}
    for phone in ("0000000000", "123", "1111111111"):
        with pytest.raises(ValidationError):
            CheckoutRequest(customer_phone=phone, **common)
    assert CheckoutRequest(customer_phone="0901234567", **common).customer_phone == "0901234567"
    with pytest.raises(ValidationError):
        ProfileUpdateIn(phone="abc123")

    _, headers = await account(["customer_support"])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers) as client:
        response = await client.get("/api/v1/admin/support/tickets")
        assert response.status_code == 200 and isinstance(response.json(), list), response.text


@pytest.mark.asyncio
async def test_shop_menu_reorder_visibility_and_custom_link():
    from app.main import app
    _, headers = await account(["platform_manage"])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers) as client:
        initial = (await client.get("/api/v1/admin/shop/navigation")).json()
        assert [item["key"] for item in initial] == ["shop", "search", "track"]
        custom = {"key": f"custom:{uuid.uuid4()}", "label": "Cứu hộ", "href": "/tram-cuu-ho", "visible": True}
        changed = [initial[2], custom, {**initial[1], "visible": False}, initial[0]]
        saved = await client.put("/api/v1/admin/shop/navigation", json={"items": changed})
        assert saved.status_code == 200, saved.text
        public = (await client.get("/api/v1/shop/navigation")).json()
        assert [item["key"] for item in public] == ["track", custom["key"], "shop"]
        bad = await client.put("/api/v1/admin/shop/navigation", json={"items": [initial[0], initial[1], {**initial[2], "key": f"custom:{uuid.uuid4()}", "href": "//outside.example"}]})
        assert bad.status_code == 422


@pytest.mark.asyncio
async def test_one_line_address_book():
    from app.main import app
    _, headers = await account([])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers) as client:
        created = await client.post("/api/v1/me/addresses", json={"recipient_name": "Khách thử",
            "recipient_phone": "0901234567", "full_address": "12 Đường Hoa, Phường 1, Thành phố Hồ Chí Minh",
            "is_default": True})
        assert created.status_code == 201, created.text
        address = created.json()
        assert address["full_address"] == "12 Đường Hoa, Phường 1, Thành phố Hồ Chí Minh"
        assert (await client.get("/api/v1/me/addresses")).json()[0]["full_address"] == address["full_address"]
        changed = await client.patch(f"/api/v1/me/addresses/{address['id']}",
            json={"full_address": "14 Đường Hoa, Phường 1, Thành phố Hồ Chí Minh"})
        assert changed.status_code == 200 and changed.json()["full_address"].startswith("14 Đường Hoa"), changed.text


@pytest.mark.asyncio
async def test_catalog_first_save_and_archive_preserves_stock_history():
    from app.main import app
    _, headers = await account(["platform_manage"])
    suffix = uuid.uuid4().hex[:8]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers) as client:
        category = await client.post("/api/v1/categories", json={"name":"V2 QA", "slug":"v2-"+suffix, "sort_order":9, "is_active":False})
        assert category.status_code == 201, category.text
        cid = category.json()["id"]
        second = await client.post("/api/v1/categories", json={"name":"V2 Next", "slug":"v2-next-"+suffix, "is_active":False})
        assert second.status_code == 201 and second.json()["sort_order"] == 10
        assert cid not in {r["id"] for r in (await client.get("/api/v1/categories")).json()}
        product = await client.post("/api/v1/products", json={"category_id":cid,"name":"Sản phẩm V2", "slug":"product-"+suffix,"pet_type":"both","status":"draft","variants":[{"sku":"V2-"+suffix,"title":"1 túi","options":{"unit":"túi"},"price":10000,"weight_grams":100}]})
        assert product.status_code == 201, product.text
        pid = product.json()["id"]; vid=product.json()["variants"][0]["id"]
        assert product.json()["variants"][0]["options"]["unit"] == "túi"
        saved = await client.patch("/api/v1/products/"+pid, json={"name":"Đã sửa ngay lần đầu","status":"active"})
        assert saved.status_code == 200 and saved.json()["name"] == "Đã sửa ngay lần đầu", saved.text
        second_variant = await client.post("/api/v1/products/"+pid+"/variants", json={"sku":"V2-TAI-"+suffix,"title":"1 tải","options":{"unit":"tải"},"price":100000,"weight_grams":1000})
        assert second_variant.status_code == 201 and second_variant.json()["options"]["unit"] == "tải", second_variant.text
        nav_category = await client.patch("/api/v1/categories/"+cid, json={"is_active":True,"show_in_nav":True,"sort_order":2})
        assert nav_category.status_code == 200 and nav_category.json()["show_in_nav"] is True
        assert next(c for c in (await client.get("/api/v1/categories")).json() if c["id"] == cid)["sort_order"] == 2
        stock = await client.get("/api/v1/products/"+pid+"/stock")
        assert stock.status_code == 200 and {v["unit"] for v in stock.json()["variants"]} == {"túi", "tải"}, stock.text
        assert (await client.get("/api/v1/admin/catalog/products")).json()[0]["name"] == "Đã sửa ngay lần đầu"
        assert (await client.delete("/api/v1/admin/records/categories/"+cid)).status_code == 409
        lot = await client.post("/api/v1/admin/lots", json={"variant_id":vid,"lot_no":"V2-LOT-"+suffix,"qty":10,"unit_cost":5000})
        assert lot.status_code == 201, lot.text
        lid=lot.json()["id"]
        images = await client.put(f"/api/v1/admin/products/{pid}/images", json=[{"r2_url":"/brand/cat-food.jpg","sort_order":0}])
        assert images.status_code == 200, images.text
        cart = await client.post("/api/v1/cart/items", json={"variant_id":vid,"qty":3})
        assert cart.status_code == 200 and cart.json()["items"][0]["qty"] == 3, cart.text
        assert cart.json()["items"][0]["image_url"] == "/brand/cat-food.jpg"
        assert (await client.delete("/api/v1/admin/records/lots/"+lid)).status_code == 409
        for expected in [5,0]:
            adjustment = await client.post("/api/v1/admin/stock/adjust", json={"lot_id":lid,"qty_delta":-5,"reason":"manual_correct","note":"Isolated QA"})
            assert adjustment.status_code == 200, adjustment.text
            rows=(await client.get("/api/v1/admin/lots")).json()
            assert next(r for r in rows if r["id"]==lid)["qty_on_hand"] == expected
        assert (await client.delete("/api/v1/admin/records/lots/"+lid)).status_code == 204
        assert lid not in {r["id"] for r in (await client.get("/api/v1/admin/lots")).json()}
        async with AsyncSessionLocal() as db:
            assert await db.scalar(select(func.count()).select_from(StockMovement).where(StockMovement.lot_id==uuid.UUID(lid))) == 3
        assert (await client.delete("/api/v1/admin/records/products/"+pid)).status_code == 204
        assert pid not in {r["id"] for r in (await client.get("/api/v1/admin/catalog/products")).json()}
        assert (await client.delete("/api/v1/admin/records/categories/"+cid)).status_code == 204
        assert cid not in {r["id"] for r in (await client.get("/api/v1/admin/catalog/categories")).json()}


@pytest.mark.asyncio
async def test_order_commit_reporting_and_archive_guards():
    from app.main import app
    user_id, headers = await account(["platform_manage"])
    _, limited = await account(["warehouse"])
    async with AsyncSessionLocal() as db:
        orders=[]
        for state,amount in [("pending",10000),("delivered",30000),("cancelled",20000)]:
            row=Order(order_code=uuid.uuid4().hex[:10].upper(), idempotency_key=uuid.uuid4().hex, user_id=user_id, customer_name="V2 QA",customer_phone="0901234567",shipping_address={}, status=state,payment_method="cod",payment_status="unpaid",subtotal_amount=amount,total_amount=amount,shipping_fee=0,discount_amount=0,created_at=datetime(2026,11,3,17,0,tzinfo=UTC))
            db.add(row); orders.append(row)
        await db.commit()
    pending, delivered, cancelled = orders
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test",headers=headers) as client:
        confirmed=await client.post(f"/api/v1/orders/{pending.id}/confirm")
        assert confirmed.status_code == 200, confirmed.text
        rows=(await client.get("/api/v1/admin/orders")).json()
        assert next(r for r in rows if r["id"]==str(pending.id))["status"]=="confirmed"
        assert (await client.delete(f"/api/v1/admin/records/orders/{pending.id}")).status_code==409
        report=await client.get("/api/v1/admin/reports/sales?date_from=2026-11-04&date_to=2026-11-04")
        assert report.status_code==200, report.text
        assert report.json()["orders"]==3 and report.json()["delivered_value"]==30000 and report.json()["ordered_value"]==40000
        assert report.json()["daily"][0]["day"]=="2026-11-04"
        day_summary=report.json()["daily"][0]
        assert day_summary["orders"]==3
        assert day_summary["delivered_orders"]==1
        assert day_summary["closed_orders"]==1
        assert day_summary["processing_orders"]==1
        assert day_summary["cod_pending_orders"]==1
        assert day_summary["handled"] is False
        assert {item["status"]: item["orders"] for item in day_summary["status_breakdown"]}=={
            "confirmed": 1, "delivered": 1, "cancelled": 1}
        detail=await client.get("/api/v1/admin/orders?date_from=2026-11-04&date_to=2026-11-04&report_metric=delivered")
        assert detail.status_code==200 and [row["id"] for row in detail.json()]==[str(delivered.id)], detail.text
        assert (await client.get("/api/v1/admin/orders?date_from=2026-11-04&date_to=2026-11-04&report_metric=paid")).json()==[]
        assert (await client.get("/api/v1/admin/reports/sales?date_from=2026-11-05&date_to=2026-11-04")).status_code==422
        assert (await client.delete(f"/api/v1/admin/records/orders/{cancelled.id}",headers=limited)).status_code==403
        assert (await client.delete(f"/api/v1/admin/records/orders/{cancelled.id}")).status_code==204
        assert str(cancelled.id) not in {r["id"] for r in (await client.get("/api/v1/admin/orders")).json()}
        # Removing a row from the list never erases historical report counts.
        assert (await client.get("/api/v1/admin/reports/sales?date_from=2026-11-04&date_to=2026-11-04")).json()["orders"]==3


@pytest.mark.asyncio
async def test_order_work_queue_and_manual_cod_receipt():
    from app.main import app
    from app.models.fulfillment import Payment
    _, headers = await account(["warehouse"])
    async with AsyncSessionLocal() as db:
        orders = []
        for state in ("shipped", "shipped", "delivered", "cancelled"):
            row = Order(order_code=uuid.uuid4().hex[:10].upper(), idempotency_key=uuid.uuid4().hex,
                customer_name="COD QA", customer_phone="0901234567", shipping_address={},
                status=state, payment_method="cod", payment_status="unpaid",
                subtotal_amount=25000, total_amount=25000)
            db.add(row); orders.append(row)
        await db.commit()
    later, immediate, unpaid_delivered, cancelled = orders
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers) as client:
        active = (await client.get("/api/v1/admin/orders?view=active&q=COD%20QA")).json()
        assert {r["id"] for r in active} == {str(later.id), str(immediate.id), str(unpaid_delivered.id)}
        assert {r["id"] for r in (await client.get("/api/v1/admin/orders?view=closed&q=COD%20QA")).json()} == {str(cancelled.id)}
        invalid = await client.post(f"/api/v1/admin/orders/{immediate.id}/delivered",
            json={"note": "Shop tự giao tận tay khách", "cod_received": True})
        assert invalid.status_code == 422
        assert (await client.get(f"/api/v1/admin/orders/{immediate.id}")).json()["status"] == "shipped"
        delivered = await client.post(f"/api/v1/admin/orders/{later.id}/delivered",
            json={"note": "Nhân viên đã giao tận tay khách"})
        assert delivered.status_code == 200 and delivered.json()["payment_status"] == "unpaid", delivered.text
        assert str(later.id) in {r["id"] for r in (await client.get("/api/v1/admin/orders?view=active&q=COD%20QA")).json()}
        assert (await client.post(f"/api/v1/admin/orders/{later.id}/cod-receipt",
            json={"note": "Hãng vận chuyển đã chuyển khoản đủ cho shop"})).status_code == 200
        assert (await client.post(f"/api/v1/admin/orders/{later.id}/cod-receipt",
            json={"note": "Không được nhận hai lần"})).status_code == 409
        immediate_result = await client.post(f"/api/v1/admin/orders/{immediate.id}/delivered",
            json={"note": "Shop tự giao tận tay khách", "cod_received": True,
                  "cod_note": "Nhân viên đã nộp đủ tiền mặt cho shop"})
        assert immediate_result.status_code == 200 and immediate_result.json()["payment_status"] == "paid", immediate_result.text
        assert {r["id"] for r in (await client.get("/api/v1/admin/orders?view=closed&q=COD%20QA")).json()} == {
            str(later.id), str(immediate.id), str(cancelled.id)}
        async with AsyncSessionLocal() as db:
            payments = (await db.scalars(select(Payment).where(Payment.order_id.in_([later.id, immediate.id])))).all()
            assert len(payments) == 2 and all(p.provider == "manual_cod" and p.actual_amount == 25000 for p in payments)


@pytest.mark.asyncio
async def test_promotion_archive_and_stock_alerts():
    from app.main import app
    _,headers=await account(["platform_manage"])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test",headers=headers) as client:
        promo=await client.post("/api/v1/admin/promotions",json={"code":"V2"+uuid.uuid4().hex[:8],"discount_type":"percentage","discount_value":10,"starts_at":"2026-11-01T00:00:00+07:00","expires_at":"2026-12-01T00:00:00+07:00"})
        assert promo.status_code==201,promo.text
        pid=promo.json()["id"]
        assert (await client.delete("/api/v1/admin/records/promotions/"+pid)).status_code==204
        assert pid not in {r["id"] for r in (await client.get("/api/v1/admin/promotions")).json()}
        assert (await client.get("/api/v1/admin/stock-alerts")).status_code==200


@pytest.mark.asyncio
async def test_rescue_cursor_page_two_has_no_missing_or_duplicate_posts():
    from app.main import app
    from app.models.community import CommunityPost
    user_id, headers = await account(["platform_manage"])
    async with AsyncSessionLocal() as db:
        for i in range(13):
            db.add(CommunityPost(author_user_id=user_id, post_type="adoption", title=f"Pagination QA {i}",
                slug="page-qa-"+uuid.uuid4().hex, pet_type="cat", province_id=1, province_name="Hà Nội",
                contact_phone="0901234567", moderation_status="approved", lifecycle_status="open",
                created_at=datetime(2026,11,4,0,0,tzinfo=UTC), expires_at=datetime.now(UTC)+timedelta(days=30)))
        await db.commit()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test",headers=headers) as client:
        first=await client.get("/api/v1/community/posts",params={"post_type":"adoption","limit":12})
        assert first.status_code==200,first.text
        assert len(first.json()["items"])==12 and first.json()["next_cursor"]
        second=await client.get("/api/v1/community/posts",params={"post_type":"adoption","limit":12,"cursor":first.json()["next_cursor"]})
        assert second.status_code==200,second.text
        assert len(second.json()["items"])==1 and second.json()["next_cursor"] is None
        ids={r["id"] for r in first.json()["items"]+second.json()["items"]}
        assert len(ids)==13
        assert (await client.get("/api/v1/community/posts?cursor=invalid")).status_code==422


@pytest.mark.asyncio
async def test_rejected_review_is_gone_on_the_next_request():
    from app.main import app
    from app.models.catalog import Category, Product, ProductVariant, Review
    from app.models.commerce import OrderItem
    user_id, headers = await account(["platform_manage"])
    async with AsyncSessionLocal() as db:
        category=Category(name="Review QA",slug=uuid.uuid4().hex)
        db.add(category); await db.flush()
        product=Product(category_id=category.id,name="Review QA",slug=uuid.uuid4().hex,pet_type="cat",status="draft")
        db.add(product); await db.flush()
        variant=ProductVariant(product_id=product.id,sku=uuid.uuid4().hex,title="QA",price=10000,weight_grams=100)
        db.add(variant)
        order=Order(order_code=uuid.uuid4().hex[:10].upper(),idempotency_key=uuid.uuid4().hex,user_id=user_id,customer_name="Review QA",customer_phone="0901234567",shipping_address={},status="delivered",payment_method="cod",payment_status="unpaid",subtotal_amount=10000,total_amount=10000)
        db.add(order); await db.flush()
        item=OrderItem(order_id=order.id,product_id=product.id,variant_id=variant.id,product_name_snapshot="Review QA",variant_title_snapshot="QA",sku_snapshot=variant.sku,weight_grams_snapshot=100,qty=1,unit_price=10000,line_total=10000)
        db.add(item); await db.flush()
        review=Review(product_id=product.id,order_item_id=item.id,user_id=user_id,reviewer_name="Review QA",rating=5,is_approved=False)
        db.add(review); await db.commit(); review_id=str(review.id)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test",headers=headers) as client:
        response=await client.post(f"/api/v1/admin/reviews/{review_id}/approve",json={"approve":False})
        assert response.status_code==200,response.text
        assert review_id not in {r["id"] for r in (await client.get("/api/v1/admin/reviews")).json()}
