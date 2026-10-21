"""Checkout and customer order endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthContext, get_auth_context, get_current_user, get_current_user_optional
from app.core.rate_limit import client_ip, enforce_rate_limit
from app.models.commerce import Order, OrderItem
from app.models.user import User
from app.modules.inventory.fefo_service import release_reservations
from app.modules.order import checkout as checkout_service
from app.modules.order.schemas import (
    CancelOrderRequest,
    CheckoutRequest,
    OrderItemOut,
    OrderOut,
    OrderTrackOut,
    mask_address,
    mask_phone,
)
from app.modules.order.state import transition_order
from app.modules.promotion import service as promo_service
from app.worker import enqueue as job_enqueue

router = APIRouter(prefix="/api/v1", tags=["orders"])


async def _load_order_out(session: AsyncSession, order_id: UUID) -> OrderOut:
    order = await session.get(Order, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Đơn không tồn tại")
    items = (
        await session.scalars(select(OrderItem).where(OrderItem.order_id == order_id))
    ).all()
    return OrderOut.from_order(order, list(items))


@router.post("/checkout", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def checkout_endpoint(
    body: CheckoutRequest,
    background_tasks: BackgroundTasks,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db),
) -> OrderOut:
    user_id = auth.user.id if auth.user else None
    order_out, jobs = await checkout_service.checkout(
        session,
        user_id=user_id,
        guest_token=auth.guest_token,
        body=body,
    )

    async def _enqueue_after_commit() -> None:
        for job in jobs:
            if job.startswith("create_vietqr_payment:"):
                oid = job.split(":", 1)[1]
                await job_enqueue.enqueue_create_vietqr_payment(UUID(oid))
            elif job.startswith("send_order_confirmation_email:"):
                oid = job.split(":", 1)[1]
                await job_enqueue.enqueue_send_order_confirmation_email(UUID(oid))

    background_tasks.add_task(_enqueue_after_commit)
    return order_out


@router.get("/orders/me", response_model=list[OrderOut])
async def list_my_orders(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=30, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[OrderOut]:
    stmt = (
        select(Order)
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    orders = (await session.scalars(stmt)).all()
    out: list[OrderOut] = []
    for order in orders:
        items = (
            await session.scalars(select(OrderItem).where(OrderItem.order_id == order.id))
        ).all()
        out.append(OrderOut.from_order(order, list(items)))
    return out


@router.get("/orders/track", response_model=OrderTrackOut)
async def track_order(
    request: Request,
    order_code: str = Query(min_length=6, max_length=12),
    phone: str = Query(min_length=8, max_length=20),
    session: AsyncSession = Depends(get_db),
) -> OrderTrackOut:
    ip = client_ip(request)
    await enforce_rate_limit(
        key=f"rl:track:{ip}:{phone}",
        limit=10,
        window_seconds=60,
    )
    order = await session.scalar(
        select(Order).where(
            Order.order_code == order_code.upper().strip(),
            Order.customer_phone == phone.strip(),
        )
    )
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn hàng")

    items = (
        await session.scalars(select(OrderItem).where(OrderItem.order_id == order.id))
    ).all()

    return OrderTrackOut(
        order_code=order.order_code,
        status=order.status,
        payment_status=order.payment_status,
        total_amount=order.total_amount,
        customer_name=order.customer_name,
        customer_phone_masked=mask_phone(order.customer_phone),
        shipping_address=mask_address(order.shipping_address),
        created_at=order.created_at,
        items=[OrderItemOut.model_validate(i) for i in items],
    )


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db),
) -> OrderOut:
    order = await session.get(Order, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Đơn không tồn tại")
    if auth.user and order.user_id == auth.user.id:
        return await _load_order_out(session, order_id)
    if auth.user and auth.user.role in ("owner", "warehouse_staff", "cskh_staff"):
        return await _load_order_out(session, order_id)
    raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền xem đơn")


@router.post("/orders/{order_id}/confirm", response_model=OrderOut)
async def confirm_order(
    order_id: UUID,
    user: User | None = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_db),
) -> OrderOut:
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    order = await session.get(Order, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Đơn không tồn tại")

    actor_type = "staff" if user.role != "customer" else "customer"
    if user.role == "customer" and order.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")

    if user.role == "customer" and order.payment_method == "vietqr" and order.payment_status != "paid":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Đơn VietQR cần thanh toán trước khi xác nhận",
        )

    await transition_order(
        session,
        order_id,
        from_status="pending",
        to_status="confirmed",
        actor_type=actor_type,
        actor_user_id=user.id,
    )
    order.reservation_expires_at = None
    await session.flush()
    return await _load_order_out(session, order_id)


@router.post("/orders/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(
    order_id: UUID,
    body: CancelOrderRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db),
) -> OrderOut:
    order = await session.get(Order, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Đơn không tồn tại")

    if order.status in ("shipped", "delivered", "cancelled", "returned"):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Không thể hủy đơn ở trạng thái này")

    is_owner = auth.user and order.user_id == auth.user.id
    is_staff = auth.user and auth.user.role in ("owner", "warehouse_staff", "cskh_staff")
    if not is_owner and not is_staff:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền hủy đơn")

    from_status = order.status
    if from_status not in ("pending", "confirmed"):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Không thể hủy đơn ở trạng thái này")

    await release_reservations(session, order_id)
    await promo_service.release_promo_on_cancel(session, order_id)
    await transition_order(
        session,
        order_id,
        from_status=from_status,
        to_status="cancelled",
        actor_type="staff" if is_staff else "customer",
        actor_user_id=auth.user.id if auth.user else None,
        note=body.reason,
    )
    order.cancel_reason = body.reason
    order.reservation_expires_at = None
    await session.flush()
    return await _load_order_out(session, order_id)
