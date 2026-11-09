"""Checkout and customer order endpoints."""

from __future__ import annotations

import secrets
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    AuthContext,
    get_auth_context,
    get_current_user,
    has_staff_permission,
    require_shop_staff as require_staff_user,
)
from app.core.rate_limit import client_ip, enforce_rate_limit
from app.core.security import hash_token
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


@router.get("/checkout/methods")
async def payment_methods():
    from app.modules.payment.payos import online_available
    return {"methods": [{"id": "cod", "label": "Thanh toán khi nhận hàng", "available": True},
                        {"id": "vietqr", "label": "Thanh toán online qua payOS", "available": online_available()}]}


@router.post("/checkout/quote")
async def quote_endpoint(body: CheckoutRequest, request: Request,
                         auth: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db)):
    await enforce_rate_limit(key=f"rl:quote:{client_ip(request)}", limit=30, window_seconds=60)
    return await checkout_service.create_quote(session, user_id=auth.user.id if auth.user else None,
                                               guest_token=auth.guest_token, body=body)


@router.get("/checkout/recover", response_model=OrderOut)
async def recover_checkout(idempotency_key: str = Query(min_length=8, max_length=100),
                           auth: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db)):
    order = await session.scalar(select(Order).where(Order.idempotency_key == idempotency_key))
    owns = order and ((auth.user and order.user_id == auth.user.id) or (
        auth.guest_token and order.user_id is None and order.guest_token_hash and secrets.compare_digest(hash_token(auth.guest_token), order.guest_token_hash)))
    if not owns:
        raise HTTPException(404, "Chưa tìm thấy đơn hàng đã đặt.")
    out = await _load_order_out(session, order.id)
    from app.modules.order.tracking import tracking_token
    out.tracking_token = tracking_token(order.id)
    return out


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
    request: Request,
    background_tasks: BackgroundTasks,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db),
) -> OrderOut:
    await enforce_rate_limit(key=f"rl:checkout:{client_ip(request)}", limit=10, window_seconds=60)
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
    from app.modules.order.tracking import tracking_token
    order_out.tracking_token = tracking_token(order_out.id)
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
    auth: AuthContext = Depends(get_auth_context),
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
    owns = order and ((auth.user and order.user_id == auth.user.id) or (
        auth.guest_token and order.guest_token_hash and secrets.compare_digest(hash_token(auth.guest_token), order.guest_token_hash)))
    if not owns:
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


class LookupIn(BaseModel):
    token: str = Field(min_length=20, max_length=2048)


class TrackingLinkIn(BaseModel):
    order_code: str = Field(min_length=6, max_length=12)
    email: EmailStr


@router.post("/orders/tracking-link")
async def request_tracking_link(body: TrackingLinkIn, request: Request, session: AsyncSession = Depends(get_db)):
    await enforce_rate_limit(key=f"rl:tracking-link:{client_ip(request)}", limit=10, window_seconds=3600)
    await enforce_rate_limit(key=f"rl:tracking-link-account:{hash_token(str(body.email).lower())}", limit=3, window_seconds=3600)
    order = await session.scalar(select(Order).where(Order.order_code == body.order_code.strip().upper(),
        Order.customer_email.ilike(str(body.email))))
    if order:
        from datetime import UTC, datetime

        from app.worker.commerce_outbox import record_job
        delivery_key = f"tracking-{order.id}-{int(datetime.now(UTC).timestamp()) // 3600}"
        await record_job(session, "send_order_confirmation_email", delivery_key,
                         {"order_id": str(order.id), "delivery_key": delivery_key})
    return {"message": "Nếu thông tin khớp với đơn hàng, liên kết tra cứu sẽ được gửi tới email nhận đơn."}


@router.post("/orders/lookup", response_model=OrderTrackOut)
async def lookup_order(body: LookupIn, request: Request, session: AsyncSession = Depends(get_db)):
    from app.modules.order.tracking import read_tracking_token
    await enforce_rate_limit(key=f"rl:lookup:{client_ip(request)}", limit=15, window_seconds=60)
    order = await session.get(Order, read_tracking_token(body.token))
    if not order:
        raise HTTPException(404, "Không tìm thấy đơn hàng.")
    items = (await session.scalars(select(OrderItem).where(OrderItem.order_id == order.id))).all()
    return OrderTrackOut(order_code=order.order_code, status=order.status, payment_status=order.payment_status,
        total_amount=order.total_amount, customer_name=order.customer_name,
        customer_phone_masked=mask_phone(order.customer_phone), shipping_address=mask_address(order.shipping_address),
        created_at=order.created_at, items=[OrderItemOut.model_validate(i) for i in items])


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
    if auth.guest_token and order.user_id is None and order.guest_token_hash and secrets.compare_digest(hash_token(auth.guest_token), order.guest_token_hash):
        return await _load_order_out(session, order_id)
    if auth.user and (has_staff_permission(auth.user, "warehouse") or has_staff_permission(auth.user, "customer_support")):
        return await _load_order_out(session, order_id)
    raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền xem đơn")


@router.get("/orders/{order_id}/payment")
async def order_payment(order_id: UUID, auth: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db)):
    from app.models.fulfillment import Payment
    await get_order(order_id, auth, session)
    payment = await session.scalar(select(Payment).where(Payment.order_id == order_id, Payment.transaction_type == "charge").order_by(Payment.created_at.desc()).limit(1))
    if not payment:
        return {"status": "not_required", "checkout_url": None}
    order = await session.get(Order, order_id)
    url = (payment.raw_response or {}).get("checkout_url") if order.status == "pending" else None
    return {"status": payment.status, "checkout_url": url}


@router.post("/orders/{order_id}/confirm", response_model=OrderOut)
async def confirm_order(
    order_id: UUID,
    user: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> OrderOut:
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Vui lòng đăng nhập để tiếp tục.")
    order = await session.scalar(select(Order).where(Order.id == order_id).with_for_update().execution_options(populate_existing=True))
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Đơn không tồn tại")

    actor_type = "staff"
    if order.payment_method != "cod" and order.payment_status not in ("paid", "overpaid"):
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
    await promo_service.consume_promo_on_paid(session, order.id)
    await session.flush()
    result = await _load_order_out(session, order_id)
    await session.commit()
    return result



@router.post("/orders/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(
    order_id: UUID,
    body: CancelOrderRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db),
) -> OrderOut:
    order = await session.scalar(select(Order).where(Order.id == order_id).with_for_update().execution_options(populate_existing=True))
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Đơn không tồn tại")

    if order.status in ("shipped", "delivered", "cancelled", "returned"):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Không thể hủy đơn ở trạng thái này")

    is_owner = auth.user and order.user_id == auth.user.id
    is_staff = auth.user and (has_staff_permission(auth.user, "warehouse") or has_staff_permission(auth.user, "customer_support"))
    if not is_owner and not is_staff:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền hủy đơn")

    from_status = order.status
    if from_status not in ("pending", "confirmed", "packed"):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Không thể hủy đơn ở trạng thái này")

    await promo_service.release_promo_on_cancel(session, order_id)
    # Older deployments deducted stock at packing. Those orders require inspection.
    from sqlalchemy import text
    deducted = await session.scalar(text("SELECT COUNT(*) FROM lot_allocations la JOIN order_items oi ON oi.id = la.order_item_id WHERE oi.order_id = :oid AND la.status = 'deducted'"), {"oid": order_id})
    if deducted:
        raise HTTPException(409, "Đơn đã xuất kho. Vui lòng liên hệ nhân viên để kiểm tra hàng trước khi hủy.")
    await release_reservations(session, order_id)
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
    if order.payment_status in ("paid", "overpaid", "underpaid"):
        from sqlalchemy import func

        from app.models.fulfillment import Payment
        from app.modules.payment.settlement import record_case
        received = await session.scalar(select(func.sum(Payment.actual_amount)).where(Payment.order_id == order_id, Payment.transaction_type == "charge"))
        await record_case(session, order_id, "refund_required", int(received or 0), str(order_id))
    await session.flush()
    result = await _load_order_out(session, order_id)
    await session.commit()
    return result
