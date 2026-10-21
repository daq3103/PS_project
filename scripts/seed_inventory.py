"""Seed inventory lots for active variants (FEFO checkout).

Usage:
  cd backend && python -m scripts.seed_inventory
  # or from repo root with DATABASE_URL set:
  python scripts/seed_inventory.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.catalog import Product, ProductVariant
from app.models.inventory import InventoryLot, StockMovement


async def seed_lots(session: AsyncSession) -> int:
    variants = (
        await session.execute(
            select(ProductVariant, Product)
            .join(Product, Product.id == ProductVariant.product_id)
            .where(ProductVariant.is_active.is_(True), Product.status == "active")
        )
    ).all()

    created = 0
    today = date.today()
    for variant, product in variants:
        existing = await session.scalar(
            select(InventoryLot.id).where(
                InventoryLot.variant_id == variant.id,
                InventoryLot.lot_no == "SEED-001",
            )
        )
        if existing:
            continue

        qty = 50
        expiry = today + timedelta(days=180 if product.has_expiry else 365)
        lot = InventoryLot(
            variant_id=variant.id,
            lot_no="SEED-001",
            manufactured_date=today - timedelta(days=30),
            expiry_date=expiry if product.has_expiry else None,
            unit_cost=max(1, variant.price // 2),
            qty_initial=qty,
            qty_on_hand=qty,
            qty_reserved=0,
            status="active",
            note="seed_inventory.py",
        )
        session.add(lot)
        await session.flush()
        session.add(
            StockMovement(
                lot_id=lot.id,
                qty_delta=qty,
                reason="lot_import",
                ref_type="lot",
                ref_id=lot.id,
                note="Initial seed stock",
            )
        )
        await session.execute(
            text("""
                UPDATE product_variants
                SET cached_available_qty = cached_available_qty + :q,
                    nearest_expiry_date = :exp,
                    updated_at = NOW()
                WHERE id = :vid
            """),
            {
                "q": qty,
                "vid": variant.id,
                "exp": lot.expiry_date,
            },
        )
        created += 1
        print(f"lot SEED-001 +{qty} for SKU {variant.sku}")

    return created


async def main() -> None:
    _ = os.environ.get("DATABASE_URL")
    async with AsyncSessionLocal() as session:
        n = await seed_lots(session)
        await session.commit()
    print(f"done — {n} lot(s) created")


if __name__ == "__main__":
    asyncio.run(main())
