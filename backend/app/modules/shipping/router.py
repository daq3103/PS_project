"""Shipping webhooks and shipment creation."""

from __future__ import annotations

import hmac
import json
from hashlib import sha256
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import require_staff_user
from app.models.commerce import Order
from app.models.fulfillment import Fulfillment
from app.models.user import User
from app.modules.shipping.mock_ghn import MockGHNProvider
from app.worker import enqueue as job_enqueue

router = APIRouter(prefix="/api/v1", tags=["shipping"])
_ghn = MockGHNProvider()


class CreateShipmentBody(BaseModel):
    carrier_code: str = Field(default="mock_ghn")
    package_count: int = Field(default=1, ge=1, le=10)


@router.post("/webhooks/ghn")
async def ghn_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    settings = get_settings()
    secret = settings.mock_ghn_webhook_secret
    if not secret:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Webhook secret not configured",
        )

    signature = request.headers.get("X-GHN-Signature") or request.headers.get("X-Signature")
    if not signature:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook signature",
        )

    body = await request.body()
    expected = hmac.new(secret.encode(), body, sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook signature",
        )

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid JSON") from exc

    event_id = str(payload.get("OrderCode") or payload.get("event_id") or payload.get("tracking_code"))
    if not event_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Missing event id")

    ins = await session.execute(
        text("""
            INSERT INTO webhook_events (provider, external_event_id, payload, process_status)
            VALUES ('mock_ghn', :eid, CAST(:payload AS jsonb), 'processed')
            ON CONFLICT (provider, external_event_id) DO NOTHING
            RETURNING id
        """),
        {"eid": event_id, "payload": json.dumps(payload)},
    )
    if ins.first() is None:
        return {"status": "duplicate_ignored"}

    tracking = str(payload.get("tracking_code") or payload.get("OrderCode") or event_id)
    carrier_status = str(payload.get("Status") or payload.get("status") or "delivering")
    internal = _ghn.map_carrier_status(carrier_status)

    ff = await session.scalar(
        select(Fulfillment).where(Fulfillment.tracking_code == tracking)
    )
    if not ff:
        return {"status": "ignored", "reason": "fulfillment_not_found"}

    ff.carrier_status = carrier_status
    ff.internal_status = internal
    if internal == "delivered":
        order = await session.get(Order, ff.order_id)
        if order and order.status == "shipped":
            from app.modules.order.state import transition_order

            await transition_order(
                session,
                order.id,
                from_status="shipped",
                to_status="delivered",
                actor_type="webhook",
                note="GHN delivered",
            )
    await session.flush()
    return {"status": "ok"}


@router.post("/orders/{order_id}/shipments", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_create_shipment(
    order_id: UUID,
    body: CreateShipmentBody,
    background_tasks: BackgroundTasks,
    _staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    order = await session.get(Order, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Đơn không tồn tại")
    if order.status not in ("confirmed", "packed", "shipped"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Đơn chưa sẵn sàng tạo vận đơn",
        )

    background_tasks.add_task(
        job_enqueue.enqueue_create_shipment,
        order_id,
        body.carrier_code,
        body.package_count,
        None,
    )
    return {"status": "enqueued", "order_id": str(order_id)}
