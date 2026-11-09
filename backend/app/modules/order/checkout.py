"""Checkout orchestration: idempotency, FEFO, COD/VietQR paths."""

from __future__ import annotations

import json
import secrets
import string
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_token
from app.models.catalog import Product, ProductVariant
from app.models.commerce import CartItem, Order, OrderItem
from app.models.fulfillment import Payment
from app.models.operations import CheckoutQuote
from app.modules.cart import service as cart_service
from app.modules.inventory.fefo_service import allocate_inventory_fefo
from app.modules.order.pricing import allocate_discount, fingerprint
from app.modules.order.schemas import CheckoutItemIn, CheckoutRequest, OrderOut
from app.modules.promotion import service as promo_service


def _gen_order_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(10))


async def _resolve_line_items(
    session: AsyncSession,
    *,
    user_id: UUID | None,
    guest_token: str | None,
    body_items: list[CheckoutItemIn] | None,
) -> list[tuple[ProductVariant, Product, int]]:
    lines: list[tuple[ProductVariant, Product, int]] = []

    if body_items:
        quantities: dict[UUID, int] = {}
        for bi in body_items:
            quantities[bi.variant_id] = quantities.get(bi.variant_id, 0) + bi.qty
        for variant_id, qty in sorted(quantities.items(), key=lambda pair: str(pair[0])):
            if qty > 99:
                raise HTTPException(422, "Mỗi mẫu sản phẩm được đặt tối đa 99 món trong một đơn.")
            variant = await session.get(ProductVariant, variant_id)
            if not variant or not variant.is_active:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Biến thể không tồn tại")
            product = await session.get(Product, variant.product_id)
            if not product or product.status != "active":
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Sản phẩm không còn bán")
            lines.append((variant, product, qty))
        return lines

    cart, _ = await cart_service._get_or_create_cart(
        session, user_id=user_id, guest_token=guest_token
    )
    cart_rows = (
        await session.execute(
            select(CartItem, ProductVariant, Product)
            .join(ProductVariant, ProductVariant.id == CartItem.variant_id)
            .join(Product, Product.id == ProductVariant.product_id)
            .where(CartItem.cart_id == cart.id)
        )
    ).all()
    if not cart_rows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Giỏ hàng trống")

    for item, variant, product in cart_rows:
        if item.qty > 99:
            raise HTTPException(422, "Mỗi mẫu sản phẩm được đặt tối đa 99 món. Vui lòng sửa lại giỏ hàng.")
        if not variant.is_active or product.status != "active":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Sản phẩm {product.name} không còn khả dụng",
            )
        lines.append((variant, product, item.qty))
    return lines


async def checkout(
    session: AsyncSession,
    *,
    user_id: UUID | None,
    guest_token: str | None,
    body: CheckoutRequest,
) -> tuple[OrderOut, list[str]]:
    """Returns order + job names to enqueue after commit."""
    request_hash = hash_token(json.dumps(body.model_dump(mode="json", exclude={"quote_id"}), sort_keys=True, separators=(",", ":")))
    guest_hash = hash_token(guest_token) if guest_token else None
    if user_id is None and guest_hash is None:
        raise HTTPException(400, "Vui lòng tải lại giỏ hàng trước khi đặt hàng.")
    # Serialize concurrent retries, including the first request before its row exists.
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": body.idempotency_key})
    existing = await session.scalar(
        select(Order).where(Order.idempotency_key == body.idempotency_key)
    )
    if existing:
        same_owner = (existing.user_id == user_id if user_id is not None else
                      existing.user_id is None and existing.guest_token_hash is not None
                      and secrets.compare_digest(existing.guest_token_hash, guest_hash))
        if not same_owner or existing.request_hash != request_hash:
            raise HTTPException(409, "Yêu cầu đặt hàng không còn hợp lệ. Vui lòng kiểm tra lại đơn hàng.")
        oi_rows = (
            await session.scalars(select(OrderItem).where(OrderItem.order_id == existing.id))
        ).all()
        return OrderOut.from_order(existing, list(oi_rows)), []

    # One lock order for both explicit-item and cart checkouts: cart, coupon, variants, lots.
    await cart_service._get_or_create_cart(session, user_id=user_id, guest_token=guest_token)
    lines = await _resolve_line_items(
        session, user_id=user_id, guest_token=guest_token, body_items=body.items
    )

    totals, promotion_id, coupon_snapshot = await price_lines(session, lines, body, user_id)
    # Re-read prices under a lock compatible with order-item foreign keys. Admin price
    # changes cannot slip in between quote validation and the persisted order snapshot.
    for variant, _product, _qty in sorted(lines, key=lambda line: str(line[0].id)):
        await session.execute(select(ProductVariant.id).where(ProductVariant.id == variant.id).with_for_update(key_share=True))
        await session.refresh(variant)
    for product in sorted({p.id: p for _v, p, _q in lines}.values(), key=lambda p: str(p.id)):
        await session.execute(select(Product.id).where(Product.id == product.id).with_for_update(read=True))
        await session.refresh(product)
        if product.status != "active":
            raise HTTPException(409, "Sản phẩm không còn được bán. Vui lòng kiểm tra lại giỏ hàng.")
    if any(not variant.is_active for variant, _p, _q in lines):
        raise HTTPException(409, "Mẫu sản phẩm không còn được bán.")
    totals, promotion_id, coupon_snapshot = await price_lines(session, lines, body, user_id)
    discount_amount = totals["discount_amount"]
    total = totals["total_amount"]
    quote = None
    if body.quote_id:
        quote = await session.scalar(select(CheckoutQuote).where(CheckoutQuote.id == body.quote_id).with_for_update())
        owner_key = str(user_id) if user_id else hash_token(guest_token)
        if (not quote or quote.owner_key != owner_key or quote.request_hash != fingerprint(body)
                or quote.expires_at <= datetime.now(UTC) or quote.order_id is not None):
            raise HTTPException(409, "Báo giá đã hết hiệu lực. Vui lòng kiểm tra lại tổng tiền.")
        if quote.totals != totals or quote.lines != line_snapshot(lines):
            raise HTTPException(409, "Giá hoặc giỏ hàng đã thay đổi. Vui lòng xem lại báo giá trước khi đặt.")
    else:
        raise HTTPException(422, "Vui lòng xem lại báo giá trước khi đặt hàng.")

    order_code = _gen_order_code()
    for _ in range(5):
        clash = await session.scalar(select(Order.id).where(Order.order_code == order_code))
        if not clash:
            break
        order_code = _gen_order_code()

    now = datetime.now(UTC)
    reservation_expires_at = now + timedelta(minutes=15) if body.payment_method == "vietqr" else now + timedelta(hours=24)
    order = Order(
        order_code=order_code, user_id=user_id, idempotency_key=body.idempotency_key,
        guest_token_hash=guest_hash if user_id is None else None, request_hash=request_hash,
        customer_name=body.customer_name, customer_phone=body.customer_phone,
        customer_email=body.customer_email, shipping_address=body.shipping_address,
        status="pending", payment_method=body.payment_method, payment_status="unpaid",
        **totals, promotion_id=promotion_id, coupon_code_snapshot=coupon_snapshot,
        reservation_expires_at=reservation_expires_at, customer_note=body.customer_note,
    )
    session.add(order)
    await session.flush()
    quote.order_id = order.id
    discounts = allocate_discount([v.price * qty for v, _p, qty in lines], discount_amount)
    order_items_for_fefo = []
    for (variant, product, qty), line_discount in zip(lines, discounts, strict=True):
        oi = OrderItem(order_id=order.id, product_id=product.id, variant_id=variant.id,
            product_name_snapshot=product.name, variant_title_snapshot=variant.title,
            sku_snapshot=variant.sku, weight_grams_snapshot=variant.weight_grams,
            qty=qty, unit_price=variant.price, line_total=variant.price * qty, discount_amount=line_discount)
        session.add(oi)
        await session.flush()
        order_items_for_fefo.append({"order_item_id": oi.id, "variant_id": variant.id, "qty": qty})
    if promotion_id:
        await promo_service.apply_promo_on_checkout(session, promotion_id=promotion_id,
            order_id=order.id, user_id=user_id, customer_phone=body.customer_phone)
    await allocate_inventory_fefo(session, order_items_for_fefo)
    jobs = []
    if body.payment_method == "vietqr":
        from app.modules.payment.payos import online_available, online_provider_code
        if not online_available():
            raise HTTPException(409, "Thanh toán trực tuyến chưa sẵn sàng. Vui lòng chọn thanh toán khi nhận hàng.")
        payment = Payment(order_id=order.id, provider=online_provider_code(), transaction_type="charge",
            idempotency_key=f"pay-{body.idempotency_key}", expected_amount=total, actual_amount=0, status="pending")
        session.add(payment)
        jobs.append(f"create_vietqr_payment:{order.id}")
    cart, _ = await cart_service._get_or_create_cart(session, user_id=user_id, guest_token=guest_token)
    await session.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    jobs.append(f"send_order_confirmation_email:{order.id}")
    from app.worker.commerce_outbox import record_job
    for job in jobs:
        task, oid = job.split(":", 1)
        await record_job(session, task, oid, {"order_id": oid})
    await session.flush()
    await session.refresh(order)
    items = (await session.scalars(select(OrderItem).where(OrderItem.order_id == order.id))).all()
    return OrderOut.from_order(order, list(items)), []


def line_snapshot(lines):
    return sorted([{"variant_id": str(v.id), "qty": qty, "price": v.price} for v, _p, qty in lines], key=lambda x: x["variant_id"])


async def price_lines(session, lines, body, user_id):
    subtotal = sum(v.price * qty for v, _p, qty in lines)
    settings = get_settings()
    weight = sum(v.weight_grams * qty for v, _p, qty in lines)
    # Shop-configured customer fee, not a fabricated quote from a real carrier.
    shipping_fee = settings.shipping_base_fee + max(1, (weight + 999) // 1000) * settings.shipping_per_kg_fee

    discount_amount = 0
    shipping_discount = 0
    promotion_id = None
    coupon_snapshot = None
    if body.promo_code:
        promo = await promo_service.validate_promo(
            session,
            code=body.promo_code,
            subtotal=subtotal,
            user_id=user_id,
            customer_phone=body.customer_phone,
        )
        discount_amount, shipping_discount = promo_service.compute_discount(
            promo, subtotal=subtotal, shipping_fee=shipping_fee
        )
        promotion_id = promo.id
        coupon_snapshot = promo.code

    total = max(0, subtotal - discount_amount + shipping_fee - shipping_discount)

    return {"subtotal_amount": subtotal, "discount_amount": discount_amount,
            "shipping_fee": shipping_fee, "shipping_discount": shipping_discount,
            "total_amount": total}, promotion_id, coupon_snapshot


async def create_quote(session, *, user_id, guest_token, body):
    if not user_id and not guest_token:
        raise HTTPException(400, "Vui lòng mở giỏ hàng trước khi xem báo giá.")
    if not body.customer_name.strip() or not body.customer_phone.strip():
        raise HTTPException(422, "Vui lòng nhập tên và số điện thoại nhận hàng.")
    full_address = str(body.shipping_address.get("full_address", "")).strip()
    parts_complete = all(str(body.shipping_address.get(k, "")).strip() for k in ("province", "district", "ward", "street"))
    if (not full_address or len(full_address) < 10) and not parts_complete:
        raise HTTPException(422, "Vui lòng nhập đầy đủ địa chỉ nhận hàng.")
    lines = await _resolve_line_items(session, user_id=user_id, guest_token=guest_token, body_items=body.items)
    totals, _, _ = await price_lines(session, lines, body, user_id)
    quote = CheckoutQuote(owner_key=str(user_id) if user_id else hash_token(guest_token),
        request_hash=fingerprint(body), totals=totals, lines=line_snapshot(lines),
        expires_at=datetime.now(UTC) + timedelta(minutes=10))
    session.add(quote)
    await session.flush()
    return {"quote_id": str(quote.id), "expires_at": quote.expires_at, **totals, "items": quote.lines}
