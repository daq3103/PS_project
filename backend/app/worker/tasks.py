"""ARQ worker tasks + cron (Weeks 3–5)."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from html import escape
from uuid import UUID

import httpx
from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.commerce import Order
from app.models.fulfillment import Fulfillment, Payment
from app.modules.analytics.service import cleanup_analytics
from app.modules.inventory.fefo_service import SELLABLE_LOT_SQL, release_reservations, shelf_params
from app.modules.order.state import transition_order
from app.modules.payment.mock_vietqr import MockVietQRProvider
from app.modules.promotion import service as promo_service
from app.modules.rescue.maintenance import cleanup_rescue_files, maintain_rescue
from app.modules.shipping.mock_ghn import MockGHNProvider
from app.worker.commerce_outbox import dispatch_commerce_jobs, record_job
from app.worker.community_tasks import (
    cleanup_community_data,
    dispatch_community_outbox,
    maintain_community_posts,
)

logger = logging.getLogger(__name__)


async def revalidate_product_cache(
    ctx: dict, product_slug: str, category_id: str | None = None
) -> dict:
    settings = get_settings()
    tags = [f"product-{product_slug}", "catalog"]
    if category_id:
        tags.append(f"category-{category_id}")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            settings.nextjs_revalidate_url,
            json={"tags": tags, "secret": settings.revalidate_secret},
        )
        resp.raise_for_status()
        body = resp.json()
        logger.info("revalidated tags=%s status=%s", tags, resp.status_code)
        return body


async def send_order_confirmation_email(ctx: dict, order_id: str, delivery_key: str | None = None) -> dict:
    oid = UUID(order_id)
    api_key = os.environ.get("RESEND_API_KEY", "")
    async with AsyncSessionLocal() as session:
        order = await session.get(Order, oid)
        if not order:
            return {"status": "missing_order"}

        if not order.customer_email:
            return {"status": "not_requested"}

        if not api_key:
            logger.info("Order email is waiting for sender configuration")
            await session.commit()
            return {"status": "skipped_no_api_key"}

        payload = {
            "from": os.environ.get("RESEND_FROM", "orders@petshop.local"),
            "to": [order.customer_email or "devnull@example.com"],
            "subject": f"Xác nhận đơn {order.order_code}",
            "html": f"<p>Cảm ơn {escape(order.customer_name)}! Mã đơn: <b>{escape(order.order_code)}</b></p>",
        }
        if get_settings().app_public_url:
            from app.modules.order.tracking import tracking_token
            url = get_settings().app_public_url.rstrip("/") + "/track-order#token=" + tracking_token(order.id)
            payload["html"] += f'<p><a href="{escape(url, quote=True)}">Theo dõi đơn hàng</a> (liên kết có hiệu lực 7 ngày).</p>'
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}", "Idempotency-Key": delivery_key or f"order-confirmation-{order.id}"},
                json=payload,
            )
            resp.raise_for_status()
        await session.commit()
        return {"status": "sent", "order_code": order.order_code}


async def create_vietqr_payment_job(ctx: dict, order_id: str) -> dict:
    oid = UUID(order_id)
    provider = MockVietQRProvider()
    async with AsyncSessionLocal() as session:
        order = await session.get(Order, oid)
        if not order:
            return {"status": "missing_order"}

        payment = await session.scalar(
            select(Payment).where(
                Payment.order_id == oid,
                Payment.provider.in_(("mock_vietqr", "payos")),
                Payment.transaction_type == "charge",
            )
        )
        if not payment:
            return {"status": "missing_payment"}

        if order.status != "pending" or order.reservation_expires_at is None or order.reservation_expires_at <= datetime.now(UTC):
            return {"status": "order_no_longer_payable"}
        if payment.provider == "payos":
            from app.modules.payment.payos import PayOSProvider
            oid, pid = order.id, payment.id
            amount, code, expiry = order.total_amount, order.order_code, order.reservation_expires_at
            if payment.external_transaction_id:
                return {"status": "already_created"}
            # End the read transaction before waiting for the provider.
            await session.commit()
            result = await PayOSProvider().create_or_get(order_code=code, amount=amount, expires_at=expiry)
            payment = await session.get(Payment, pid)
            payment.external_transaction_id = result["paymentLinkId"]
            payment.raw_response = {"checkout_url": result["checkoutUrl"], "provider_order_code": int(code, 36)}
            await session.commit()
            return {"status": "created"}

        if payment.external_transaction_id and payment.qr_code_url:
            await session.commit()
            return {"status": "already_created"}

        result = await provider.create_payment(
            order_id=str(order.id),
            order_code=order.order_code,
            amount=int(order.total_amount),
            idempotency_key=payment.idempotency_key,
        )
        payment.external_transaction_id = result["external_transaction_id"]
        payment.qr_code_url = result["qr_code_url"]
        payment.raw_response = result.get("raw_response") or {}
        await session.commit()
        return {"status": "created", "qr": payment.qr_code_url}


async def create_shipment_job(
    ctx: dict,
    order_id: str,
    carrier_code: str = "mock_ghn",
    package_count: int = 1,
    total_weight_grams: int | None = None,
) -> dict:
    oid = UUID(order_id)
    if get_settings().app_env != "development" or carrier_code != "mock_ghn":
        raise RuntimeError("Mock shipping is disabled outside development")
    provider = MockGHNProvider()
    async with AsyncSessionLocal() as session:
        order = await session.scalar(select(Order).where(Order.id == oid).with_for_update())
        if not order:
            return {"status": "missing_order"}
        if order.status not in ("confirmed", "packed", "shipped"):
            return {"status": "order_no_longer_shippable"}

        existing = await session.scalar(
            select(Fulfillment).where(
                Fulfillment.order_id == oid,
                Fulfillment.carrier_code == carrier_code,
                Fulfillment.tracking_code.isnot(None),
            )
        )
        if existing and existing.tracking_code:
            await session.commit()
            return {"status": "already_created", "tracking": existing.tracking_code}

        max_attempt = await session.scalar(
            select(func.max(Fulfillment.attempt_no)).where(
                Fulfillment.order_id == oid,
                Fulfillment.carrier_code == carrier_code,
            )
        )
        attempt_no = int(max_attempt or 0) + 1

        if total_weight_grams is not None and int(total_weight_grams) > 0:
            weight = int(total_weight_grams)
        else:
            weight = await session.scalar(
                text("""
                    SELECT COALESCE(SUM(weight_grams_snapshot * qty), 500)
                    FROM order_items WHERE order_id = :oid
                """),
                {"oid": oid},
            )
            weight = int(weight or 500)
        packages = max(1, min(10, int(package_count or 1)))
        cod = order.total_amount if order.payment_method == "cod" else 0

        ship = await provider.create_shipment(
            order_id=str(order.id),
            shipping_address=order.shipping_address,
            total_weight_grams=weight,
            cod_amount=int(cod),
            attempt_no=attempt_no,
        )

        ff = Fulfillment(
            order_id=oid,
            carrier_code=carrier_code,
            tracking_code=ship["tracking_code"],
            cod_amount=cod,
            total_weight_grams=weight,
            package_count=packages,
            carrier_status=ship.get("carrier_status"),
            internal_status=provider.map_carrier_status(
                ship.get("carrier_status") or "ready_to_pick"
            ),
            label_print_url=ship.get("label_print_url"),
            shipping_fee_charged_by_carrier=ship.get("shipping_fee_charged_by_carrier"),
            attempt_no=attempt_no,
        )
        session.add(ff)
        await session.commit()
        return {"status": "created", "tracking": ff.tracking_code}


async def expire_pending_reservations(ctx: dict) -> dict:
    now = datetime.now(UTC)
    expired = 0
    async with AsyncSessionLocal() as session:
        orders = (
            await session.scalars(
                select(Order).where(
                    Order.status == "pending",
                    Order.payment_status.in_(("unpaid", "underpaid")),
                    Order.reservation_expires_at.isnot(None),
                    Order.reservation_expires_at < now,
                ).order_by(Order.id).limit(100).with_for_update(skip_locked=True)
            )
        ).all()
        for order in orders:
            await promo_service.release_promo_on_cancel(session, order.id)
            await release_reservations(session, order.id)
            await transition_order(
                session,
                order.id,
                from_status="pending",
                to_status="cancelled",
                actor_type="system_cron",
                note="Reservation expired (15m)",
            )
            order.cancel_reason = "Reservation expired"
            order.reservation_expires_at = None
            if order.payment_status == "underpaid":
                from app.modules.payment.settlement import record_case
                received = await session.scalar(select(func.sum(Payment.actual_amount)).where(Payment.order_id == order.id, Payment.transaction_type == "charge"))
                await record_case(session, order.id, "refund_required", int(received or 0), str(order.id))
            expired += 1
        await session.commit()
    return {"expired_orders": expired}


async def cleanup_guest_carts(ctx: dict) -> dict:
    cutoff = datetime.now(UTC) - timedelta(days=60)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                DELETE FROM carts
                WHERE guest_token IS NOT NULL
                  AND user_id IS NULL
                  AND updated_at < :cutoff
            """),
            {"cutoff": cutoff},
        )
        await session.commit()
        return {"deleted_carts": result.rowcount}  # type: ignore[attr-defined]


async def reenqueue_pending_jobs(ctx: dict) -> dict:
    """Re-enqueue stale pending payments / orders missing email."""

    payments = 0
    emails = 0
    async with AsyncSessionLocal() as session:
        stale = datetime.now(UTC) - timedelta(minutes=2)
        pay_rows = (
            await session.scalars(
                select(Payment).where(
                    Payment.status == "pending",
                    Payment.provider == "mock_vietqr",
                    Payment.qr_code_url.is_(None),
                    Payment.created_at < stale,
                )
            )
        ).all()
        for p in pay_rows:
            await record_job(session, "create_vietqr_payment", str(p.order_id), {"order_id": str(p.order_id)})
            payments += 1

        # Confirmation emails are recorded once in commerce_jobs during checkout.
        # Do not resend all recent orders on every recovery scan.
        await session.commit()
    return {"payments": payments, "emails_queued": emails}


async def reconcile_cached_available_qty(ctx: dict) -> dict:
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("""
                WITH locked AS (
                    SELECT id FROM product_variants ORDER BY id FOR NO KEY UPDATE SKIP LOCKED
                )
                UPDATE product_variants pv
                SET cached_available_qty = COALESCE((
                    SELECT SUM(GREATEST(0, il.qty_on_hand - il.qty_reserved))
                    FROM inventory_lots il
                    WHERE il.variant_id = pv.id AND il.status = 'active'
                    """ + SELLABLE_LOT_SQL + """
                ), 0),
                updated_at = NOW()
                FROM locked WHERE pv.id = locked.id
            """), shelf_params()
        )
        await session.commit()
    logger.info("reconcile_cached_available_qty completed (stub/full refresh)")
    return {"status": "ok"}




class WorkerSettings:
    max_jobs = max(1, min(10, int(os.environ.get("WORKER_MAX_JOBS", "10"))))
    functions = [
        maintain_rescue,
        cleanup_rescue_files,
        dispatch_commerce_jobs,
        cleanup_analytics,
        dispatch_community_outbox,
        maintain_community_posts,
        cleanup_community_data,
        revalidate_product_cache,
        send_order_confirmation_email,
        create_vietqr_payment_job,
        create_shipment_job,
        expire_pending_reservations,
        cleanup_guest_carts,
        reenqueue_pending_jobs,
        reconcile_cached_available_qty,
    ]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_queue_url_with_auth)
    max_tries = 5
    job_timeout = 120
    cron_jobs = [
        cron(maintain_rescue, minute=set(range(60))),
        cron(cleanup_rescue_files, hour=3, minute=30),
        cron(dispatch_commerce_jobs, second={0, 15, 30, 45}),
        cron(cleanup_analytics, hour=3, minute=45),
        cron(dispatch_community_outbox, minute=set(range(60))),
        cron(maintain_community_posts, minute={5, 20, 35, 50}),
        cron(cleanup_community_data, hour=3, minute=15),
        cron(expire_pending_reservations, minute={0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44, 46, 48, 50, 52, 54, 56, 58}),
        cron(cleanup_guest_carts, hour=3, minute=0),
        cron(reenqueue_pending_jobs, minute={1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35, 37, 39, 41, 43, 45, 47, 49, 51, 53, 55, 57, 59}),
        cron(reconcile_cached_available_qty, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
    ]
