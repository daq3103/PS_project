"""Payment webhooks (VietQR mock)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.commerce import Order
from app.models.fulfillment import Payment
from app.modules.order.state import transition_order
from app.modules.payment.mock_vietqr import MockVietQRProvider
from app.modules.promotion import service as promo_service

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

_provider = MockVietQRProvider()


@router.post("/vietqr")
async def vietqr_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    body = await request.body()
    signature = request.headers.get("X-Signature", "")
    timestamp = request.headers.get("X-Timestamp", "")

    if not _provider.verify_webhook(body=body, signature=signature, timestamp=timestamp):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid JSON") from exc

    event_id = str(payload.get("event_id") or payload.get("transaction_id") or "")
    if not event_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Missing event_id")

    ins = await session.execute(
        text("""
            INSERT INTO webhook_events (provider, external_event_id, payload, process_status)
            VALUES ('mock_vietqr', :eid, CAST(:payload AS jsonb), 'processed')
            ON CONFLICT (provider, external_event_id) DO NOTHING
            RETURNING id
        """),
        {"eid": event_id, "payload": json.dumps(payload)},
    )
    if ins.first() is None:
        return {"status": "duplicate_ignored"}

    ext_tx = str(payload.get("transaction_id") or payload.get("external_transaction_id") or "")
    actual_amount = int(payload.get("amount") or payload.get("actual_amount") or 0)

    payment = await session.scalar(
        select(Payment).where(
            Payment.external_transaction_id == ext_tx,
            Payment.provider == "mock_vietqr",
        )
    )
    if not payment:
        payment = await session.scalar(
            select(Payment).where(Payment.idempotency_key == payload.get("idempotency_key"))
        )
    if not payment:
        await session.execute(
            text("""
                UPDATE webhook_events SET process_status = 'failed', error_message = :msg
                WHERE provider = 'mock_vietqr' AND external_event_id = :eid
            """),
            {"eid": event_id, "msg": "payment not found"},
        )
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Payment not found")

    pay_status = _provider.classify_amount(
        expected=int(payment.expected_amount),
        actual=actual_amount,
    )
    payment.actual_amount = actual_amount
    payment.status = pay_status
    payment.raw_response = {**(payment.raw_response or {}), "webhook": payload}

    order = await session.get(Order, payment.order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Order not found")

    if pay_status == "succeeded":
        payment.paid_at = datetime.now(UTC)
        order.payment_status = "paid"
        if order.status == "pending":
            await transition_order(
                session,
                order.id,
                from_status="pending",
                to_status="confirmed",
                actor_type="webhook",
                note="VietQR paid",
            )
            order.reservation_expires_at = None
        await promo_service.consume_promo_on_paid(session, order.id)
    elif pay_status == "underpaid":
        order.payment_status = "underpaid"
    elif pay_status == "overpaid":
        order.payment_status = "overpaid"
        payment.paid_at = datetime.now(UTC)
        if order.status == "pending":
            await transition_order(
                session,
                order.id,
                from_status="pending",
                to_status="confirmed",
                actor_type="webhook",
                note="VietQR overpaid (tolerance)",
            )
            order.reservation_expires_at = None

    await session.flush()
    return {"status": "ok", "payment_status": pay_status}
