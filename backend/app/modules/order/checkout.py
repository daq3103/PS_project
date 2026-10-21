"""Checkout orchestration: idempotency, FEFO, COD/VietQR paths."""

from __future__ import annotations

import secrets
import string
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Product, ProductVariant
from app.models.commerce import CartItem, Order, OrderItem
from app.models.fulfillment import Payment
from app.modules.cart import service as cart_service
from app.modules.inventory.fefo_service import allocate_inventory_fefo
from app.modules.order.schemas import CheckoutItemIn, CheckoutRequest, OrderOut
from app.modules.order.state import transition_order
from app.modules.promotion import service as promo_service
from app.modules.shipping.mock_ghn import MockGHNProvider


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
        for bi in body_items:
            variant = await session.get(ProductVariant, bi.variant_id)
            if not variant or not variant.is_active:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Biến thể không tồn tại")
            if variant.cached_available_qty < bi.qty:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail=f"Không đủ tồn kho cho biến thể {variant.id}",
                )
            product = await session.get(Product, variant.product_id)
            if not product or product.status != "active":
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Sản phẩm không còn bán")
            lines.append((variant, product, bi.qty))
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
        if not variant.is_active or product.status != "active":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Sản phẩm {product.name} không còn khả dụng",
            )
        if variant.cached_available_qty < item.qty:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"Không đủ tồn kho cho {product.name}",
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
    existing = await session.scalar(
        select(Order).where(Order.idempotency_key == body.idempotency_key)
    )
    if existing:
        oi_rows = (
            await session.scalars(select(OrderItem).where(OrderItem.order_id == existing.id))
        ).all()
        return OrderOut.from_order(existing, list(oi_rows)), []

    lines = await _resolve_line_items(
        session, user_id=user_id, guest_token=guest_token, body_items=body.items
    )

    subtotal = sum(v.price * qty for v, _p, qty in lines)
    shipping_provider = MockGHNProvider()
    shipping_fee = await shipping_provider.quote_fee(
        shipping_address=body.shipping_address,
        total_weight_grams=sum(v.weight_grams * qty for v, _p, qty in lines),
    )

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

    order_code = _gen_order_code()
    for _ in range(5):
        clash = await session.scalar(select(Order.id).where(Order.order_code == order_code))
        if not clash:
            break
        order_code = _gen_order_code()

    now = datetime.now(UTC)
    reservation_expires_at: datetime | None = None
    payment_status = "unpaid"

    if body.payment_method == "vietqr":
        reservation_expires_at = now + timedelta(minutes=15)

    order = Order(
        order_code=order_code,
        user_id=user_id,
        idempotency_key=body.idempotency_key,
        customer_name=body.customer_name,
        customer_phone=body.customer_phone,
        customer_email=body.customer_email,
        shipping_address=body.shipping_address,
        status="pending",
        payment_method=body.payment_method,
        payment_status=payment_status,
        subtotal_amount=subtotal,
        discount_amount=discount_amount,
        shipping_fee=shipping_fee,
        shipping_discount=shipping_discount,
        total_amount=total,
        promotion_id=promotion_id,
        coupon_code_snapshot=coupon_snapshot,
        reservation_expires_at=reservation_expires_at,
        customer_note=body.customer_note,
    )
    session.add(order)
    await session.flush()

    order_items_for_fefo: list[dict] = []
    for variant, product, qty in lines:
        oi = OrderItem(
            order_id=order.id,
            product_id=product.id,
            variant_id=variant.id,
            product_name_snapshot=product.name,
            variant_title_snapshot=variant.title,
            sku_snapshot=variant.sku,
            weight_grams_snapshot=variant.weight_grams,
            qty=qty,
            unit_price=variant.price,
            line_total=variant.price * qty,
        )
        session.add(oi)
        await session.flush()
        order_items_for_fefo.append(
            {"order_item_id": oi.id, "variant_id": variant.id, "qty": qty}
        )

    if promotion_id:
        await promo_service.apply_promo_on_checkout(
            session,
            promotion_id=promotion_id,
            order_id=order.id,
            user_id=user_id,
            customer_phone=body.customer_phone,
        )

    await allocate_inventory_fefo(session, order_items_for_fefo)

    if body.payment_method == "cod":
        await transition_order(
            session,
            order.id,
            from_status="pending",
            to_status="confirmed",
            actor_type="system_cron",
            note="Auto-confirm COD (MVP)",
        )
        order.status = "confirmed"
        order.reservation_expires_at = None

    jobs: list[str] = []

    if body.payment_method == "vietqr":
        payment = Payment(
            order_id=order.id,
            provider="mock_vietqr",
            transaction_type="charge",
            idempotency_key=f"pay-{body.idempotency_key}",
            expected_amount=total,
            actual_amount=0,
            status="pending",
        )
        session.add(payment)
        await session.flush()
        jobs.append(f"create_vietqr_payment:{order.id}")

    # Clear cart
    cart, _ = await cart_service._get_or_create_cart(
        session, user_id=user_id, guest_token=guest_token
    )
    await session.execute(delete(CartItem).where(CartItem.cart_id == cart.id))

    jobs.append(f"send_order_confirmation_email:{order.id}")

    await session.refresh(order)
    oi_rows = (
        await session.scalars(select(OrderItem).where(OrderItem.order_id == order.id))
    ).all()
    return OrderOut.from_order(order, list(oi_rows)), jobs
