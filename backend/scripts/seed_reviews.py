"""Seed pending product reviews for admin moderation demo.

Usage (inside fastapi-api container or with DATABASE_URL):
  python scripts/seed_reviews.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

_SCRIPT = Path(__file__).resolve().parent
if (_SCRIPT.parent / "app").is_dir():
    BACKEND = _SCRIPT.parent  # backend/scripts/...
elif (_SCRIPT.parent / "backend" / "app").is_dir():
    BACKEND = _SCRIPT.parent / "backend"  # repo/scripts/...
else:
    raise SystemExit("Cannot locate backend/app")
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.catalog import Product, ProductVariant, Review
from app.models.commerce import Order, OrderItem


SAMPLES = [
    ("Minh Anh", 5, "Thức ăn thơm, mèo nhà mình ăn ngon."),
    ("Tuấn", 4, "Giao nhanh, đóng gói ổn. Sẽ mua lại."),
    ("Lan", 3, "Ổn trong tầm giá, hơi nhỏ so với mô tả."),
]


async def ensure_order_item(session: AsyncSession) -> OrderItem | None:
    existing = await session.scalar(select(OrderItem).limit(1))
    if existing:
        return existing

    row = (
        await session.execute(
            select(Product, ProductVariant)
            .join(ProductVariant, ProductVariant.product_id == Product.id)
            .where(Product.status == "active", ProductVariant.is_active.is_(True))
            .limit(1)
        )
    ).first()
    if not row:
        return None
    product, variant = row
    order = Order(
        order_code=f"SR{uuid4().hex[:10].upper()}",  # 12 chars
        status="delivered",
        payment_method="cod",
        payment_status="cod_pending",
        customer_name="Seed Reviewer",
        customer_phone="0900000001",
        shipping_address={
            "province": "HN",
            "district": "Cau Giay",
            "ward": "Dich Vong",
            "street": "1 Demo",
        },
        subtotal_amount=variant.price,
        discount_amount=0,
        shipping_fee=0,
        total_amount=variant.price,
        idempotency_key=f"seed-review-{uuid4()}",
    )
    session.add(order)
    await session.flush()
    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        variant_id=variant.id,
        product_name_snapshot=product.name,
        variant_title_snapshot=variant.title,
        sku_snapshot=variant.sku,
        weight_grams_snapshot=variant.weight_grams,
        qty=1,
        unit_price=variant.price,
        line_total=variant.price,
    )
    session.add(item)
    await session.flush()
    return item


async def seed(session: AsyncSession) -> int:
    items = (await session.scalars(select(OrderItem).limit(20))).all()
    if not items:
        item = await ensure_order_item(session)
        items = [item] if item else []
    if not items:
        print("NO_PRODUCTS_OR_ITEMS")
        return 0

    created = 0
    for i, sample in enumerate(SAMPLES):
        name, rating, content = sample
        item = items[i % len(items)]
        already = await session.scalar(
            select(Review.id).where(Review.order_item_id == item.id)
        )
        if already:
            # pick another synthetic item if this one already reviewed
            continue
        session.add(
            Review(
                product_id=item.product_id,
                order_item_id=item.id,
                reviewer_name=name,
                rating=rating,
                content=content,
                is_approved=False,
            )
        )
        created += 1
        if created >= len(SAMPLES):
            break

    # If first items already had reviews, create extra order items for remaining samples
    if created < len(SAMPLES):
        base = items[0]
        for name, rating, content in SAMPLES[created:]:
            extra = OrderItem(
                order_id=base.order_id,
                product_id=base.product_id,
                variant_id=base.variant_id,
                product_name_snapshot=base.product_name_snapshot,
                variant_title_snapshot=base.variant_title_snapshot,
                sku_snapshot=f"{base.sku_snapshot}-R{created}",
                weight_grams_snapshot=base.weight_grams_snapshot,
                qty=1,
                unit_price=base.unit_price,
                line_total=base.unit_price,
            )
            session.add(extra)
            await session.flush()
            session.add(
                Review(
                    product_id=extra.product_id,
                    order_item_id=extra.id,
                    reviewer_name=name,
                    rating=rating,
                    content=content,
                    is_approved=False,
                )
            )
            created += 1

    await session.commit()
    return created


async def main() -> None:
    async with AsyncSessionLocal() as session:
        n = await seed(session)
        print(f"CREATED {n} pending reviews")


if __name__ == "__main__":
    asyncio.run(main())
