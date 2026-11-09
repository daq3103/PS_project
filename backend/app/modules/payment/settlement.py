"""Payment and expiry serialize on the order; exceptions remain visible to operators."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.models.commerce import Order
from app.models.fulfillment import Payment
from app.models.operations import OperationCase
from app.modules.order.state import transition_order
from app.modules.promotion.service import consume_promo_on_paid


async def record_case(db, order_id, kind, amount, reference):
    await db.execute(select(Order.id).where(Order.id == order_id).with_for_update())
    cases = (
        await db.scalars(
            select(OperationCase)
            .where(OperationCase.order_id == order_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).all()
    settled = sum(c.amount for c in cases if c.status == "resolved")
    target = max(0, amount - settled)
    current = next((c for c in cases if c.kind == kind and c.status == "open"), None)
    if kind == "refund_required":
        # Cancellation subsumes an outstanding overpayment. Never request both refunds.
        for case in cases:
            if case.kind == "overpayment" and case.status == "open":
                case.status = "superseded"
    if current:
        current.amount = target
        if not target:
            current.status = "superseded"
    elif target:
        db.add(
            OperationCase(
                business_key=f"{kind}:{reference}:{settled}",
                order_id=order_id,
                kind=kind,
                amount=target,
                status="open",
            )
        )
    await db.flush()


async def apply_receipt(db, payment_id, amount: int, *, cumulative=False):
    original = await db.get(Payment, payment_id)
    order = await db.scalar(
        select(Order)
        .where(Order.id == original.order_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    payment = await db.scalar(
        select(Payment)
        .where(Payment.id == payment_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if cumulative:
        payment.actual_amount = max(int(payment.actual_amount or 0), amount)
    else:
        payment.actual_amount = int(payment.actual_amount or 0) + amount
    actual = payment.actual_amount
    expected = payment.expected_amount
    if actual < expected:
        payment.status = "underpaid"
        if order.payment_status not in ("paid", "overpaid"):
            order.payment_status = "underpaid"
        if order.status == "cancelled":
            await record_case(db, order.id, "refund_required", actual, str(order.id))
        await db.flush()
        return "underpaid"
    payment.status = "succeeded" if actual == expected else "overpaid"
    payment.paid_at = payment.paid_at or datetime.now(UTC)
    order.payment_status = "paid" if actual == expected else "overpaid"
    if order.status == "pending":
        await transition_order(
            db, order.id, "pending", "confirmed", "webhook", note="Đã xác nhận khoản thanh toán"
        )
        order.reservation_expires_at = None
        await consume_promo_on_paid(db, order.id)
    if order.status == "cancelled":
        # Do not reopen a cancelled order or invent stock after the reservation was released.
        await record_case(db, order.id, "refund_required", actual, str(order.id))
    elif actual > expected:
        await record_case(db, order.id, "overpayment", actual - expected, str(order.id))
    await db.flush()
    return payment.status
