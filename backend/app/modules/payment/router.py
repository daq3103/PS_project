"""Authenticated payment callbacks with transaction/reference deduplication."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.commerce import Order
from app.models.fulfillment import Payment, WebhookEvent
from app.modules.payment.mock_vietqr import MockVietQRProvider
from app.modules.payment.payos import online_available, verify_data
from app.modules.payment.settlement import apply_receipt

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


async def parse_body(request):
    body = await request.body()
    if len(body) > 65536:
        raise HTTPException(413, "Nội dung thông báo vượt giới hạn.")
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError()
        return body, payload
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(400, "Thông báo thanh toán không hợp lệ.") from exc


async def save_event(db, provider, reference, payload):
    # Manual shelter bookkeeping and shop callbacks must not claim the same receipt.
    from sqlalchemy import text

    from app.models.rescue import RescueLedger
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {"key":"external-receipt:"+reference})
    if await db.scalar(select(RescueLedger.id).where(RescueLedger.reference == reference)):
        raise HTTPException(409, "Giao dịch đã có trong sổ cứu hộ. Cần đối soát đúng nguồn nhận.")
    result = await db.execute(
        insert(WebhookEvent)
        .values(
            provider=provider,
            external_event_id=reference,
            payload=payload,
            process_status="processed",
        )
        .on_conflict_do_nothing(index_elements=["provider", "external_event_id"])
        .returning(WebhookEvent.id)
    )
    return result.scalar_one_or_none()


@router.post("/vietqr")
async def vietqr_webhook(request: Request, session: AsyncSession = Depends(get_db)):
    if get_settings().app_env != "development" or get_settings().payment_provider != "mock":
        raise HTTPException(404, "Không tìm thấy chức năng này.")
    body, payload = await parse_body(request)
    provider = MockVietQRProvider()
    if not provider.verify_webhook(
        body=body,
        signature=request.headers.get("X-Signature", ""),
        timestamp=request.headers.get("X-Timestamp", ""),
    ):
        raise HTTPException(401, "Chữ ký thông báo thanh toán không hợp lệ.")
    reference = str(payload.get("transaction_id") or payload.get("external_transaction_id") or "")
    amount = payload.get("amount", payload.get("actual_amount"))
    if not reference or len(reference) > 150 or type(amount) is not int or amount <= 0:
        raise HTTPException(400, "Thông tin giao dịch không hợp lệ.")
    payment = await session.scalar(
        select(Payment).where(
            Payment.provider == "mock_vietqr", Payment.external_transaction_id == reference
        )
    )
    if not payment:
        raise HTTPException(404, "Không tìm thấy giao dịch.")
    if not await save_event(
        session, "mock_vietqr", reference, {"amount": amount, "reference": reference}
    ):
        await session.commit()
        return {"status": "duplicate_ignored"}
    result = await apply_receipt(session, payment.id, amount, cumulative=True)
    await session.commit()
    return {"status": "ok", "payment_status": result}


@router.post("/payos")
async def payos_webhook(request: Request, session: AsyncSession = Depends(get_db)):
    if get_settings().payment_provider != "payos" or not online_available():
        raise HTTPException(503, "Thanh toán trực tuyến chưa được cấu hình.")
    _, payload = await parse_body(request)
    data = payload.get("data")
    if not isinstance(data, dict) or not verify_data(data, payload.get("signature", "")):
        raise HTTPException(401, "Chữ ký thông báo thanh toán không hợp lệ.")
    if data.get("code") != "00":
        return {"status": "ignored_unsuccessful"}
    reference, amount, provider_code = (
        data.get("reference"),
        data.get("amount"),
        data.get("orderCode"),
    )
    if (
        not isinstance(reference, str)
        or not 1 <= len(reference) <= 150
        or type(amount) is not int
        or amount <= 0
        or type(provider_code) is not int
        or provider_code <= 0
        or data.get("currency") != "VND"
    ):
        raise HTTPException(400, "Thông tin giao dịch không hợp lệ.")
    # Mapping is lossless for the ten base36 digits generated for shop order codes.
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    n, code = provider_code, ""
    while n:
        n, rem = divmod(n, 36)
        code = alphabet[rem] + code
    code = code.zfill(10)
    payment = await session.scalar(
        select(Payment)
        .join(Order, Order.id == Payment.order_id)
        .where(
            Order.order_code == code,
            Payment.provider == "payos",
            Payment.transaction_type == "charge",
        )
    )
    if (
        payment
        and payment.external_transaction_id
        and payment.external_transaction_id != data.get("paymentLinkId")
    ):
        raise HTTPException(409, "Mã liên kết thanh toán không khớp.")
    event_id = await save_event(
        session,
        "payos",
        reference,
        {"reference": reference, "amount": amount, "orderCode": provider_code, "currency": "VND"},
    )
    if not event_id:
        await session.commit()
        return {"status": "duplicate_ignored"}
    if not payment:
        event = await session.get(WebhookEvent, event_id)
        event.process_status = "failed"
        event.error_message = "payment_not_found"
        await session.commit()
        return {"status": "recorded_unmatched"}
    result = await apply_receipt(session, payment.id, amount)
    await session.commit()
    return {"status": "ok", "payment_status": result}
