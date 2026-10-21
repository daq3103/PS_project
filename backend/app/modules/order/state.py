"""Order status transitions with optimistic locking (design v1.3)."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commerce import Order, OrderStatusHistory


async def transition_order(
    session: AsyncSession,
    order_id: UUID,
    from_status: str,
    to_status: str,
    actor_type: str,
    actor_user_id: UUID | None = None,
    note: str | None = None,
) -> Order:
    result = await session.execute(
        update(Order)
        .where(Order.id == order_id, Order.status == from_status)
        .values(status=to_status)
    )
    if result.rowcount != 1:  # type: ignore[attr-defined]
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Không thể chuyển trạng thái từ {from_status} sang {to_status}",
        )
    order = await session.get(Order, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Đơn hàng không tồn tại")

    session.add(
        OrderStatusHistory(
            order_id=order_id,
            from_status=from_status,
            to_status=to_status,
            actor_user_id=actor_user_id,
            actor_type=actor_type,
            note=note,
        )
    )
    await session.flush()
    return order
