"""Plan acceptance tests against a disposable PostgreSQL database, never the shop DB."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, update
from test_community import sessions, user

from app.models.catalog import Category, Product, ProductVariant
from app.models.commerce import Order, Promotion
from app.models.fulfillment import Payment
from app.models.inventory import InventoryLot, StockMovement
from app.models.operations import CommerceJob, OperationCase
from app.modules.order.checkout import checkout, create_quote
from app.modules.order.pricing import allocate_discount
from app.modules.order.schemas import CheckoutItemIn, CheckoutRequest

pytestmark = pytest.mark.skipif(
    not os.environ.get("COMMUNITY_TEST_DATABASE"), reason="isolated PostgreSQL required"
)


async def catalog(factory, *, qty=5, expiry=True, price=100000):
    async with factory() as db:
        category = Category(name="Plan QA", slug=uuid4().hex)
        db.add(category)
        await db.flush()
        product = Product(
            name="Thức ăn mèo",
            slug=uuid4().hex,
            category_id=category.id,
            pet_type="cat",
            status="active",
            has_expiry=expiry,
        )
        db.add(product)
        await db.flush()
        variant = ProductVariant(
            product_id=product.id,
            sku="QA-" + uuid4().hex,
            title="Túi 2kg",
            price=price,
            weight_grams=2000,
            cached_available_qty=qty,
        )
        db.add(variant)
        await db.flush()
        lot = InventoryLot(
            variant_id=variant.id,
            lot_no=uuid4().hex,
            qty_initial=qty,
            qty_on_hand=qty,
            qty_reserved=0,
            unit_cost=50000,
            status="active",
            expiry_date=(datetime.now(UTC) + timedelta(days=90)).date() if expiry else None,
        )
        db.add(lot)
        await db.commit()
        return product, variant, lot


def body(variant, **kwargs):
    return CheckoutRequest(
        idempotency_key=uuid4().hex,
        customer_name="QA customer",
        customer_phone="0900000000",
        shipping_address={
            "province": "Hà Nội",
            "district": "QA",
            "ward": "QA",
            "street": "QA street",
        },
        payment_method="cod",
        items=[CheckoutItemIn(variant_id=variant.id, qty=1)],
        **kwargs,
    )


async def quoted(factory, customer, request):
    with patch(
        "app.modules.shipping.mock_ghn.MockGHNProvider.quote_fee", new=AsyncMock(return_value=30000)
    ):
        async with factory() as db:
            quote = await create_quote(db, user_id=customer.id, guest_token=None, body=request)
            await db.commit()
    return request.model_copy(update={"quote_id": quote["quote_id"]})


async def place(factory, customer, request):
    with patch(
        "app.modules.shipping.mock_ghn.MockGHNProvider.quote_fee", new=AsyncMock(return_value=30000)
    ):
        async with factory() as db:
            try:
                result, _ = await checkout(db, user_id=customer.id, guest_token=None, body=request)
                await db.commit()
                return result
            except HTTPException as exc:
                await db.rollback()
                return exc.status_code


@pytest.mark.asyncio
async def test_last_item_concurrent_and_idempotent_checkout():
    factory = sessions()
    customers = [await user(factory), await user(factory)]
    _, variant, lot = await catalog(factory, qty=1)
    requests = [await quoted(factory, customer, body(variant)) for customer in customers]
    results = await asyncio.gather(*(place(factory, customer, r) for customer, r in zip(customers, requests, strict=True)))
    assert sum(not isinstance(r, int) for r in results) == 1
    assert 409 in results
    winner = next(i for i, r in enumerate(results) if not isinstance(r, int))
    again = await place(factory, customers[winner], requests[winner])
    assert again.id == results[winner].id
    assert again.status == "pending"  # COD needs staff confirmation.
    async with factory() as db:
        assert (await db.get(InventoryLot, lot.id)).qty_reserved == 1
        assert (
            await db.scalar(
                select(func.count())
                .select_from(CommerceJob)
                .where(CommerceJob.business_key.like(f"%{again.id}"))
            )
            == 1
        )


@pytest.mark.asyncio
async def test_quote_expiry_price_change_and_cross_customer():
    factory = sessions()
    customer = await user(factory)
    other = await user(factory)
    _, variant, _ = await catalog(factory)
    request = await quoted(factory, customer, body(variant))
    assert await place(factory, other, request) == 409
    async with factory() as db:
        await db.execute(
            update(ProductVariant).where(ProductVariant.id == variant.id).values(price=120000)
        )
        await db.commit()
    assert await place(factory, customer, request) == 409
    fresh = await quoted(factory, customer, body(variant))
    from app.models.operations import CheckoutQuote

    async with factory() as db:
        await db.execute(
            update(CheckoutQuote)
            .where(CheckoutQuote.id == fresh.quote_id)
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await db.commit()
    assert await place(factory, customer, fresh) == 409


@pytest.mark.asyncio
async def test_expired_and_missing_expiry_never_allocated():
    from app.modules.inventory.fefo_service import _refresh_variant_cache

    factory = sessions()
    customer = await user(factory)
    _, variant, lot = await catalog(factory, qty=2)
    request = await quoted(factory, customer, body(variant))
    async with factory() as db:
        await db.execute(
            update(InventoryLot)
            .where(InventoryLot.id == lot.id)
            .values(expiry_date=(datetime.now(UTC) - timedelta(days=1)).date())
        )
        await db.commit()
    assert await place(factory, customer, request) == 409
    async with factory() as db:
        await db.execute(
            update(InventoryLot).where(InventoryLot.id == lot.id).values(expiry_date=None)
        )
        await _refresh_variant_cache(db, variant.id)
        await db.commit()
        await db.refresh(await db.get(ProductVariant, variant.id))
        assert (await db.get(ProductVariant, variant.id)).cached_available_qty == 0


@pytest.mark.asyncio
async def test_coupon_per_customer_cannot_race():
    factory = sessions()
    customer = await user(factory)
    _, variant, _ = await catalog(factory, qty=3)
    code = "QA" + uuid4().hex[:12].upper()
    async with factory() as db:
        promo = Promotion(
            code=code,
            discount_type="percentage",
            discount_value=10,
            usage_limit=10,
            usage_limit_per_user=1,
            starts_at=datetime.now(UTC) - timedelta(days=1),
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        db.add(promo)
        await db.commit()
    requests = [await quoted(factory, customer, body(variant, promo_code=code)) for _ in range(2)]
    results = await asyncio.gather(*(place(factory, customer, r) for r in requests))
    assert sum(not isinstance(r, int) for r in results) == 1
    async with factory() as db:
        assert (await db.get(Promotion, promo.id)).used_count == 1


@pytest.mark.asyncio
async def test_pack_retains_stock_handover_deducts_once():
    from app.modules.admin.router import pack_order, ship_order
    from app.modules.order.router import confirm_order

    factory = sessions()
    customer = await user(factory)
    warehouse = await user(factory, "warehouse_staff")
    _, variant, lot = await catalog(factory)
    order = await place(factory, customer, await quoted(factory, customer, body(variant)))
    async with factory() as db:
        await confirm_order(order.id, warehouse, db)
        await db.commit()
    async with factory() as db:
        await pack_order(order.id, warehouse, db)
        await db.commit()
        row = await db.get(InventoryLot, lot.id)
        assert row.qty_on_hand == 5 and row.qty_reserved == 1
    async with factory() as db:
        await ship_order(order.id, warehouse, db)
        await db.commit()
    async with factory() as db:
        row = await db.get(InventoryLot, lot.id)
        assert row.qty_on_hand == 4 and row.qty_reserved == 0
        with pytest.raises(HTTPException):
            await ship_order(order.id, warehouse, db)
        await db.rollback()
        assert (
            await db.scalar(
                select(func.count())
                .select_from(StockMovement)
                .where(StockMovement.ref_id == order.id, StockMovement.reason == "order_deduct")
            )
            == 1
        )


@pytest.mark.asyncio
async def test_cancel_release_once_and_late_payment_stays_cancelled():
    from app.core.deps import AuthContext
    from app.modules.order.router import cancel_order
    from app.modules.order.schemas import CancelOrderRequest
    from app.modules.payment.settlement import apply_receipt

    factory = sessions()
    customer = await user(factory)
    _, variant, lot = await catalog(factory)
    order = await place(factory, customer, await quoted(factory, customer, body(variant)))
    async with factory() as db:
        await cancel_order(
            order.id, CancelOrderRequest(reason="QA cancellation"), AuthContext(customer, None), db
        )
        await db.commit()
    async with factory() as db:
        with pytest.raises(HTTPException):
            await cancel_order(order.id, CancelOrderRequest(), AuthContext(customer, None), db)
        await db.rollback()
        row = await db.get(InventoryLot, lot.id)
        assert row.qty_on_hand == 5 and row.qty_reserved == 0
        payment = Payment(
            order_id=order.id,
            provider="payos",
            transaction_type="charge",
            idempotency_key=uuid4().hex,
            expected_amount=order.total_amount,
            actual_amount=0,
        )
        db.add(payment)
        await db.commit()
        await apply_receipt(db, payment.id, order.total_amount)
        await db.commit()
        assert (await db.get(Order, order.id)).status == "cancelled"
        case = await db.scalar(select(OperationCase).where(OperationCase.order_id == order.id))
        assert case and case.amount == order.total_amount


@pytest.mark.asyncio
async def test_search_sort_global_and_accent_sku_filters():
    from app.modules.catalog.service import list_products

    factory = sessions()
    p1, v1, _ = await catalog(factory, price=900000)
    p2, _, _ = await catalog(factory, price=100000)
    async with factory() as db:
        marker = uuid4().hex
        await db.execute(
            update(Product)
            .where(Product.id.in_([p1.id, p2.id]))
            .values(name="Thức ăn mèo " + marker)
        )
        await db.commit()
        rows = await list_products(
            db, q="thuc an meo " + marker, sort="price_asc", limit=1, status_filter="active"
        )
        assert rows[0].id == p2.id
        rows = await list_products(db, q=v1.sku, status_filter="active")
        assert [r.id for r in rows] == [p1.id]


@pytest.mark.asyncio
async def test_support_ownership_and_staff_permissions(monkeypatch):
    from app.core.database import get_db
    from app.core.security import create_access_token
    from app.main import app

    factory = sessions()
    customer = await user(factory)
    other = await user(factory)
    staff = await user(factory, "cskh_staff")
    warehouse = await user(factory, "warehouse_staff")
    monkeypatch.setattr("app.modules.order.support_router.enforce_rate_limit", AsyncMock())

    async def database():
        async with factory() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    app.dependency_overrides[get_db] = database

    def headers(u):
        return {"Authorization": "Bearer " + create_access_token(subject=str(u.id), role=u.role)}

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/v1/support/tickets",
                headers=headers(customer),
                json={
                    "subject": "Đơn chưa nhận",
                    "content": "Tôi muốn hỏi về tình trạng đơn hàng.",
                },
            )
            assert r.status_code == 201, r.text
            tid = r.json()["id"]
            for u in (other, warehouse):
                assert (
                    await client.get(f"/api/v1/support/tickets/{tid}", headers=headers(u))
                ).status_code == 404
            assert (
                await client.get("/api/v1/admin/support/tickets", headers=headers(warehouse))
            ).status_code == 403
            assert (
                await client.post(
                    f"/api/v1/support/tickets/{tid}/messages",
                    headers=headers(staff),
                    json={"content": "Chúng tôi đã tiếp nhận và đang kiểm tra."},
                )
            ).status_code == 201
            detail = (
                await client.get(f"/api/v1/support/tickets/{tid}", headers=headers(customer))
            ).json()
            assert detail["status"] == "waiting_customer" and len(detail["messages"]) == 2
            assert (
                await client.patch(
                    f"/api/v1/admin/support/tickets/{tid}",
                    headers=headers(staff),
                    json={"status": "closed"},
                )
            ).status_code == 200
            assert (
                await client.post(
                    f"/api/v1/support/tickets/{tid}/messages",
                    headers=headers(customer),
                    json={"content": "test"},
                )
            ).status_code == 409
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_discount_rounding_never_exceeds_line_and_totals_match():
    for totals in ([1, 1, 1, 1], [360000, 60000], [0, 10, 0], [100, 2, 3]):
        for discount in (0, 1, sum(totals) // 2, sum(totals)):
            parts = allocate_discount(list(totals), discount)
            assert sum(parts) == discount and all(
                0 <= a <= b for a, b in zip(parts, totals, strict=True)
            )


def test_tracking_token_scope_and_tampering():
    from app.modules.order.tracking import read_tracking_token, tracking_token

    oid = uuid4()
    token = tracking_token(oid)
    assert read_tracking_token(token) == oid
    with pytest.raises(HTTPException):
        read_tracking_token(token[:-4] + "AAAA")


def test_payos_official_signature_vector():
    from app.modules.payment.payos import signature

    # Public example vector from payOS documentation, not a shop credential.
    data = {
        "orderCode": 123,
        "amount": 3000,
        "description": "VQRIO123",
        "accountNumber": "12345678",
        "reference": "TF230204212323",
        "transactionDateTime": "2023-02-04 18:25:00",
        "currency": "VND",
        "paymentLinkId": "124c33293c43417ab7879e14c8d9eb18",
        "code": "00",
        "desc": "Thành công",
        "counterAccountBankId": "",
        "counterAccountBankName": "",
        "counterAccountName": "",
        "counterAccountNumber": "",
        "virtualAccountName": "",
        "virtualAccountNumber": "",
    }
    key = "1a54716c8f0efb2744fb28b6e38b25da7f67a925d98bc1c18bd8faaecadd7675"
    assert (
        signature(data, key) == "412e915d2871504ed31be63c8f62a149a4410d34c4c42affc9006ef9917eaa03"
    )


@pytest.mark.asyncio
async def test_payos_webhook_dedup_and_underpayment(monkeypatch):
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.main import app
    from app.modules.payment.payos import signature

    factory = sessions()
    customer = await user(factory)
    _, variant, _ = await catalog(factory)
    order = await place(factory, customer, await quoted(factory, customer, body(variant)))
    settings = get_settings()
    for name, value in {
        "payment_provider": "payos",
        "payos_client_id": "qa",
        "payos_api_key": "qa",
        "payos_checksum_key": "qa-synthetic-key",
        "app_public_url": "https://qa.example.com",
    }.items():
        monkeypatch.setattr(settings, name, value)
    async with factory() as db:
        payment = Payment(
            order_id=order.id,
            provider="payos",
            transaction_type="charge",
            idempotency_key=uuid4().hex,
            expected_amount=order.total_amount,
            actual_amount=0,
            external_transaction_id="a" * 32,
        )
        db.add(payment)
        await db.commit()

    async def database():
        async with factory() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    app.dependency_overrides[get_db] = database
    data = {
        "orderCode": int(order.order_code, 36),
        "reference": uuid4().hex,
        "amount": 1,
        "code": "00",
        "currency": "VND",
        "paymentLinkId": "a" * 32,
    }
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            request = {"data": data, "signature": "invalid"}
            assert (await client.post("/api/v1/webhooks/payos", json=request)).status_code == 401
            request["signature"] = signature(data, settings.payos_checksum_key)
            response = await client.post("/api/v1/webhooks/payos", json=request)
            assert response.status_code == 200 and response.json()["payment_status"] == "underpaid"
            assert (await client.post("/api/v1/webhooks/payos", json=request)).json()[
                "status"
            ] == "duplicate_ignored"
            data.update(reference=uuid4().hex, amount=order.total_amount - 1)
            request["signature"] = signature(data, settings.payos_checksum_key)
            assert (await client.post("/api/v1/webhooks/payos", json=request)).json()[
                "payment_status"
            ] == "succeeded"
            data.update(reference=uuid4().hex, amount=100)
            request["signature"] = signature(data, settings.payos_checksum_key)
            assert (await client.post("/api/v1/webhooks/payos", json=request)).json()[
                "payment_status"
            ] == "overpaid"
        async with factory() as db:
            assert (await db.get(Order, order.id)).status == "confirmed"
            assert (await db.get(Payment, payment.id)).actual_amount == order.total_amount + 100
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_outbox_recovers_expired_lease_and_preserves_failed_work(monkeypatch):
    from app.worker.commerce_outbox import dispatch_commerce_jobs, record_job

    factory = sessions()
    monkeypatch.setattr("app.worker.commerce_outbox.AsyncSessionLocal", factory)
    handler = AsyncMock(return_value={"status": "sent"})
    monkeypatch.setattr("app.worker.tasks.send_order_confirmation_email", handler)
    reference = uuid4().hex
    async with factory() as db:
        await record_job(db, "send_order_confirmation_email", reference, {"order_id": reference})
        job = await db.scalar(
            select(CommerceJob).where(
                CommerceJob.business_key == f"send_order_confirmation_email:{reference}"
            )
        )
        job.status = "running"
        job.attempts = 1
        job.lease_until = datetime.now(UTC) - timedelta(seconds=5)
        job.created_at = datetime(2000, 1, 1, tzinfo=UTC)
        await db.commit()
    await dispatch_commerce_jobs({})
    async with factory() as db:
        assert (await db.get(CommerceJob, job.id)).status == "completed"
    await dispatch_commerce_jobs({})
    assert sum(call.kwargs.get("order_id") == reference for call in handler.call_args_list) == 1
    reference2 = uuid4().hex
    async with factory() as db:
        await record_job(db, "send_order_confirmation_email", reference2, {"order_id": reference2})
        failed = await db.scalar(
            select(CommerceJob).where(
                CommerceJob.business_key == f"send_order_confirmation_email:{reference2}"
            )
        )
        failed.attempts = 4
        failed.created_at = datetime(2000, 1, 1, tzinfo=UTC)
        await db.commit()
    handler.side_effect = RuntimeError("sensitive provider response must not be saved")
    await dispatch_commerce_jobs({})
    async with factory() as db:
        persisted = await db.get(CommerceJob, failed.id)
        assert persisted.status == "failed" and persisted.last_error == "RuntimeError"


@pytest.mark.asyncio
async def test_payment_expiry_race_has_one_consistent_outcome(monkeypatch):
    from app.modules.payment.settlement import apply_receipt
    from app.worker.tasks import expire_pending_reservations

    factory = sessions()
    customer = await user(factory)
    monkeypatch.setattr("app.worker.tasks.AsyncSessionLocal", factory)
    _, variant, lot = await catalog(factory)
    order = await place(factory, customer, await quoted(factory, customer, body(variant)))
    async with factory() as db:
        await db.execute(
            update(Order)
            .where(Order.id == order.id)
            .values(reservation_expires_at=datetime.now(UTC) - timedelta(seconds=10))
        )
        payment = Payment(
            order_id=order.id,
            provider="payos",
            transaction_type="charge",
            idempotency_key=uuid4().hex,
            expected_amount=order.total_amount,
            actual_amount=0,
        )
        db.add(payment)
        await db.commit()

    async def receive():
        async with factory() as db:
            await apply_receipt(db, payment.id, order.total_amount)
            await db.commit()

    await asyncio.gather(receive(), expire_pending_reservations({}))
    async with factory() as db:
        final = await db.get(Order, order.id)
        stock = await db.get(InventoryLot, lot.id)
        assert final.payment_status == "paid"
        if final.status == "confirmed":
            assert stock.qty_reserved == 1
        else:
            assert final.status == "cancelled" and stock.qty_reserved == 0
            assert await db.scalar(
                select(OperationCase.id).where(OperationCase.order_id == order.id)
            )


@pytest.mark.asyncio
async def test_refund_cases_do_not_duplicate_obligations():
    from app.modules.payment.settlement import record_case

    factory = sessions()
    customer = await user(factory)
    _, variant, _ = await catalog(factory)
    order = await place(factory, customer, await quoted(factory, customer, body(variant)))
    async with factory() as db:
        await record_case(db, order.id, "overpayment", 1000, str(order.id))
        await db.commit()
        await record_case(db, order.id, "refund_required", order.total_amount + 1000, str(order.id))
        await db.commit()
        rows = (
            await db.scalars(select(OperationCase).where(OperationCase.order_id == order.id))
        ).all()
        assert sum(c.amount for c in rows if c.status == "open") == order.total_amount + 1000
        current = next(c for c in rows if c.status == "open")
        current.status = "resolved"
        await db.commit()
        await record_case(db, order.id, "refund_required", order.total_amount + 2000, str(order.id))
        await db.commit()
        rows = (
            await db.scalars(select(OperationCase).where(OperationCase.order_id == order.id))
        ).all()
        assert sum(c.amount for c in rows if c.status == "open") == 1000


@pytest.mark.asyncio
async def test_manual_shipping_and_guest_tracking_do_not_expose_other_orders(monkeypatch):
    from starlette.requests import Request

    from app.core.deps import AuthContext
    from app.modules.admin.router import ManualShipmentIn, manual_shipment
    from app.modules.order.router import track_order

    factory = sessions()
    customer = await user(factory)
    other = await user(factory)
    warehouse = await user(factory, "warehouse_staff")
    _, variant, _ = await catalog(factory)
    order = await place(factory, customer, await quoted(factory, customer, body(variant)))
    request = Request(
        {"type": "http", "method": "GET", "path": "/", "headers": [], "client": ("127.0.0.1", 1234)}
    )
    monkeypatch.setattr("app.modules.order.router.enforce_rate_limit", AsyncMock())
    async with factory() as db:
        with pytest.raises(HTTPException):
            await track_order(request, order.order_code, "0900000000", AuthContext(other, None), db)
        await db.rollback()
        assert (
            await track_order(
                request, order.order_code, "0900000000", AuthContext(customer, None), db
            )
        ).order_code == order.order_code
        from app.modules.order.router import confirm_order

        await confirm_order(order.id, warehouse, db)
        await manual_shipment(
            order.id,
            ManualShipmentIn(
                carrier_code="ghn", tracking_code="QA" + uuid4().hex, total_weight_grams=2200
            ),
            warehouse,
            db,
        )
        await db.commit()
        with pytest.raises(HTTPException):
            await manual_shipment(
                order.id,
                ManualShipmentIn(
                    carrier_code="ghn", tracking_code="QA" + uuid4().hex, total_weight_grams=2200
                ),
                warehouse,
                db,
            )
        await db.rollback()
