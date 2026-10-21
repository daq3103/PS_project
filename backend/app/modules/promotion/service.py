"""Promotion apply / release at checkout (design v1.3 §4.6)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commerce import Promotion, PromotionUsage


async def validate_promo(
    session: AsyncSession,
    *,
    code: str,
    subtotal: int,
    user_id: UUID | None,
    customer_phone: str,
) -> Promotion:
    now = datetime.now(UTC)
    promo = await session.scalar(
        select(Promotion).where(Promotion.code == code.upper().strip())
    )
    if not promo or not promo.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Mã giảm giá không hợp lệ")
    if promo.starts_at > now or promo.expires_at < now:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Mã giảm giá đã hết hạn")
    if subtotal < promo.min_order_subtotal:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Đơn tối thiểu {promo.min_order_subtotal:,}đ để dùng mã này",
        )
    if promo.usage_limit is not None and promo.used_count >= promo.usage_limit:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Mã đã hết lượt sử dụng")

    if promo.usage_limit_per_user:
        per_user = (
            await session.execute(
                text("""
                    SELECT COUNT(*) FROM promotion_usages
                    WHERE promotion_id = :pid
                      AND customer_phone = :phone
                      AND status IN ('reserved', 'consumed')
                """),
                {"pid": promo.id, "phone": customer_phone},
            )
        ).scalar_one()
        if user_id:
            per_user_user = (
                await session.execute(
                    text("""
                        SELECT COUNT(*) FROM promotion_usages
                        WHERE promotion_id = :pid
                          AND user_id = :uid
                          AND status IN ('reserved', 'consumed')
                    """),
                    {"pid": promo.id, "uid": user_id},
                )
            ).scalar_one()
            per_user = max(int(per_user), int(per_user_user))
        if int(per_user) >= promo.usage_limit_per_user:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Bạn đã dùng hết lượt cho mã này",
            )
    return promo


def compute_discount(promo: Promotion, *, subtotal: int, shipping_fee: int) -> tuple[int, int]:
    """Return (discount_amount, shipping_discount)."""
    if promo.discount_type == "free_shipping":
        ship_disc = shipping_fee
        return 0, ship_disc
    if promo.discount_type == "fixed_amount":
        return min(promo.discount_value, subtotal), 0
    # percentage
    raw = subtotal * promo.discount_value // 100
    if promo.max_discount_amount is not None:
        raw = min(raw, promo.max_discount_amount)
    return min(raw, subtotal), 0


async def apply_promo_on_checkout(
    session: AsyncSession,
    *,
    promotion_id: UUID,
    order_id: UUID,
    user_id: UUID | None,
    customer_phone: str,
) -> None:
    upd = await session.execute(
        text("""
            UPDATE promotions
            SET used_count = used_count + 1
            WHERE id = :pid
              AND is_active = TRUE
              AND (usage_limit IS NULL OR used_count < usage_limit)
            RETURNING id
        """),
        {"pid": promotion_id},
    )
    if upd.first() is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Mã giảm giá không còn khả dụng")

    session.add(
        PromotionUsage(
            promotion_id=promotion_id,
            order_id=order_id,
            user_id=user_id,
            customer_phone=customer_phone,
            status="reserved",
        )
    )
    await session.flush()


async def release_promo_on_cancel(session: AsyncSession, order_id: UUID) -> None:
    usage = await session.scalar(
        select(PromotionUsage).where(
            PromotionUsage.order_id == order_id,
            PromotionUsage.status == "reserved",
        )
    )
    if not usage:
        return
    await session.execute(
        text("""
            UPDATE promotions
            SET used_count = GREATEST(0, used_count - 1)
            WHERE id = :pid
        """),
        {"pid": usage.promotion_id},
    )
    usage.status = "released"
    await session.flush()


async def consume_promo_on_paid(session: AsyncSession, order_id: UUID) -> None:
    usage = await session.scalar(
        select(PromotionUsage).where(
            PromotionUsage.order_id == order_id,
            PromotionUsage.status == "reserved",
        )
    )
    if usage:
        usage.status = "consumed"
        await session.flush()
