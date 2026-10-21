"""Enqueue ARQ jobs AFTER DB commit (pattern 4.4)."""

from __future__ import annotations

from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import get_settings


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_queue_url_with_auth)


async def enqueue_revalidate_product(
    product_slug: str, category_id: str | None = None
) -> None:
    redis = await create_pool(_redis_settings())
    try:
        await redis.enqueue_job(
            "revalidate_product_cache",
            product_slug,
            category_id,
        )
    finally:
        await redis.aclose()


async def enqueue_after_commit(job_name: str, *args, **kwargs) -> None:
    redis = await create_pool(_redis_settings())
    try:
        await redis.enqueue_job(job_name, *args, **kwargs)
    finally:
        await redis.aclose()


async def enqueue_send_order_confirmation_email(order_id: UUID) -> None:
    await enqueue_after_commit("send_order_confirmation_email", str(order_id))


async def enqueue_create_vietqr_payment(order_id: UUID) -> None:
    await enqueue_after_commit("create_vietqr_payment_job", str(order_id))


async def enqueue_create_shipment(
    order_id: UUID,
    carrier_code: str = "mock_ghn",
    package_count: int = 1,
    total_weight_grams: int | None = None,
) -> None:
    await enqueue_after_commit(
        "create_shipment_job",
        str(order_id),
        carrier_code,
        package_count,
        total_weight_grams,
    )
