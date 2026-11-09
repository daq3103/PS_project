"""FEFO inventory allocation, release, and pack deduct (design v1.3 §4.2)."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

# One predicate for allocation, cache reconciliation and import/adjustment.
SELLABLE_LOT_SQL = """
    AND (il.expiry_date IS NULL OR il.expiry_date >
         (NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date + CAST(:shelf_days AS integer))
    AND (il.expiry_date IS NOT NULL OR NOT EXISTS (
        SELECT 1 FROM product_variants ev JOIN products ep ON ep.id = ev.product_id
        WHERE ev.id = il.variant_id AND ep.has_expiry = TRUE
    ))
"""


def shelf_params() -> dict:
    return {"shelf_days": get_settings().inventory_min_shelf_life_days}

_INSUFFICIENT = "Không đủ tồn kho cho một hoặc nhiều sản phẩm"


async def _refresh_variant_cache(session: AsyncSession, variant_id: UUID) -> None:
    await session.execute(
        text("""
            UPDATE product_variants pv
            SET cached_available_qty = COALESCE((
                SELECT SUM(GREATEST(0, il.qty_on_hand - il.qty_reserved))
                FROM inventory_lots il
                WHERE il.variant_id = pv.id AND il.status = 'active'
                """ + SELLABLE_LOT_SQL + """
            ), 0),
            updated_at = NOW()
            WHERE pv.id = :vid
        """),
        {"vid": variant_id, **shelf_params()},
    )


async def allocate_inventory_fefo(
    session: AsyncSession,
    order_items: list[dict],
) -> None:
    """Allocate lots FEFO per line item. Items: order_item_id, variant_id, qty (UUIDs as str or UUID)."""
    sorted_items = sorted(order_items, key=lambda x: str(x["variant_id"]))
    # All stock mutations lock variants before lots, in stable order.
    for vid in sorted({str(line["variant_id"]) for line in sorted_items}):
        # NO KEY UPDATE is compatible with FK KEY SHARE locks taken by order_items.
        await session.execute(text("SELECT id FROM product_variants WHERE id = :vid FOR NO KEY UPDATE"), {"vid": UUID(vid)})

    for line in sorted_items:
        order_item_id = line["order_item_id"]
        if isinstance(order_item_id, str):
            order_item_id = UUID(order_item_id)
        variant_id = line["variant_id"]
        if isinstance(variant_id, str):
            variant_id = UUID(variant_id)
        needed = int(line["qty"])

        existing = await session.execute(
            text("""
                SELECT COALESCE(SUM(qty), 0) AS reserved_qty
                FROM lot_allocations
                WHERE order_item_id = :oi AND status = 'reserved'
            """),
            {"oi": order_item_id},
        )
        already = int(existing.scalar_one())
        needed -= already
        if needed <= 0:
            continue

        while needed > 0:
            lot_row = (
                await session.execute(
                    text("""
                        SELECT il.id, il.unit_cost, (il.qty_on_hand - il.qty_reserved) AS avail
                        FROM inventory_lots il
                        WHERE il.variant_id = :vid
                          AND il.status = 'active'
                          AND (il.qty_on_hand - il.qty_reserved) > 0
                          """ + SELLABLE_LOT_SQL + """
                        ORDER BY il.expiry_date ASC NULLS LAST, il.created_at ASC, il.id
                        LIMIT 1
                        FOR UPDATE OF il
                    """),
                    {"vid": variant_id, **shelf_params()},
                )
            ).first()

            if not lot_row:
                raise HTTPException(status.HTTP_409_CONFLICT, detail=_INSUFFICIENT)

            lot_id, unit_cost, avail = lot_row[0], lot_row[1], int(lot_row[2])
            take = min(needed, avail)

            ins = await session.execute(
                text("""
                    INSERT INTO lot_allocations (
                        order_item_id, lot_id, qty, unit_cost_snapshot, status
                    )
                    VALUES (:oi, :lot, :qty, :cost, 'reserved')
                    ON CONFLICT (order_item_id, lot_id) DO NOTHING
                    RETURNING id, qty
                """),
                {
                    "oi": order_item_id,
                    "lot": lot_id,
                    "qty": take,
                    "cost": unit_cost,
                },
            )
            inserted = ins.first()
            if inserted:
                upd = await session.execute(
                    text("""
                        UPDATE inventory_lots
                        SET qty_reserved = qty_reserved + :q, updated_at = NOW()
                        WHERE id = :lot
                          AND (qty_on_hand - qty_reserved) >= :q
                    """),
                    {"q": take, "lot": lot_id},
                )
                if upd.rowcount != 1:  # type: ignore[attr-defined]
                    raise HTTPException(status.HTTP_409_CONFLICT, detail=_INSUFFICIENT)

                await session.execute(
                    text("""
                        UPDATE product_variants
                        SET cached_available_qty = GREATEST(0, cached_available_qty - :q),
                            updated_at = NOW()
                        WHERE id = :vid
                    """),
                    {"q": take, "vid": variant_id},
                )
                needed -= take
            else:
                existing_line = (
                    await session.execute(
                        text("""
                            SELECT qty FROM lot_allocations
                            WHERE order_item_id = :oi AND lot_id = :lot AND status = 'reserved'
                        """),
                        {"oi": order_item_id, "lot": lot_id},
                    )
                ).scalar_one_or_none()
                if existing_line:
                    needed -= int(existing_line)
                else:
                    raise HTTPException(status.HTTP_409_CONFLICT, detail=_INSUFFICIENT)
        await _refresh_variant_cache(session, variant_id)


async def release_reservations(session: AsyncSession, order_id: UUID) -> None:
    """Release reserved allocations (cancel / expiry)."""
    await _lock_order_stock(session, order_id)
    rows = (
        await session.execute(
            text("""
                SELECT la.id, la.lot_id, la.qty, la.status, il.variant_id
                FROM lot_allocations la
                JOIN order_items oi ON oi.id = la.order_item_id
                JOIN inventory_lots il ON il.id = la.lot_id
                WHERE oi.order_id = :oid AND la.status = 'reserved'
            """),
            {"oid": order_id},
        )
    ).all()

    variants_touched: set[UUID] = set()
    for _alloc_id, lot_id, qty, st, variant_id in rows:
        if st != "reserved":
            continue
        qty = int(qty)
        await session.execute(
            text("""
                UPDATE inventory_lots
                SET qty_reserved = qty_reserved - :q, updated_at = NOW()
                WHERE id = :lot AND qty_reserved >= :q
            """),
            {"q": qty, "lot": lot_id},
        )
        await session.execute(
            text("""
                UPDATE lot_allocations
                SET status = 'released', updated_at = NOW()
                WHERE id = :id AND status = 'reserved'
            """),
            {"id": _alloc_id},
        )
        # A release changes reservations, not physical stock. Its trace is the allocation;
        # adding a positive stock movement here would falsely report an extra receipt.
        await session.execute(
            text("""
                UPDATE product_variants
                SET cached_available_qty = cached_available_qty + :q, updated_at = NOW()
                WHERE id = :vid
            """),
            {"q": qty, "vid": variant_id},
        )
        variants_touched.add(variant_id)

    for vid in variants_touched:
        await _refresh_variant_cache(session, vid)


async def deduct_on_pack(session: AsyncSession, order_id: UUID) -> None:
    """Deduct at carrier handover (legacy function name retained for compatibility)."""
    await _lock_order_stock(session, order_id)
    invalid = await session.scalar(text("""
        SELECT COUNT(*) FROM lot_allocations la
        JOIN order_items oi ON oi.id = la.order_item_id
        JOIN inventory_lots il ON il.id = la.lot_id
        WHERE oi.order_id = :oid AND la.status = 'reserved'
          AND NOT (il.status = 'active' """ + SELLABLE_LOT_SQL + """ )
    """), {"oid": order_id, **shelf_params()})
    if invalid:
        raise HTTPException(409, "Lô hàng không còn đủ điều kiện giao. Vui lòng kiểm tra lại kho.")
    rows = (
        await session.execute(
            text("""
                SELECT la.id, la.lot_id, la.qty, il.variant_id
                FROM lot_allocations la
                JOIN order_items oi ON oi.id = la.order_item_id
                JOIN inventory_lots il ON il.id = la.lot_id
                WHERE oi.order_id = :oid AND la.status = 'reserved'
            """),
            {"oid": order_id},
        )
    ).all()

    for alloc_id, lot_id, qty, variant_id in rows:
        qty = int(qty)
        upd = await session.execute(
            text("""
                UPDATE inventory_lots
                SET qty_on_hand = qty_on_hand - :q,
                    qty_reserved = qty_reserved - :q,
                    updated_at = NOW(),
                    status = CASE
                        WHEN qty_on_hand - :q <= 0 THEN 'depleted'
                        ELSE status
                    END
                WHERE id = :lot
                  AND qty_on_hand >= :q
                  AND qty_reserved >= :q
            """),
            {"q": qty, "lot": lot_id},
        )
        if upd.rowcount != 1:  # type: ignore[attr-defined]
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Không thể trừ kho khi đóng gói",
            )

        await session.execute(
            text("""
                UPDATE lot_allocations
                SET status = 'deducted', updated_at = NOW()
                WHERE id = :id AND status = 'reserved'
            """),
            {"id": alloc_id},
        )
        await session.execute(
            text("""
                INSERT INTO stock_movements (lot_id, qty_delta, reason, ref_type, ref_id, note)
                VALUES (:lot, :delta, 'order_deduct', 'order', :oid, 'Packed — on-hand deduct')
            """),
            {"lot": lot_id, "delta": -qty, "oid": order_id},
        )
        await _refresh_variant_cache(session, variant_id)


async def _lock_order_stock(session: AsyncSession, order_id: UUID) -> None:
    await session.execute(text("SELECT id FROM orders WHERE id = :oid FOR UPDATE"), {"oid": order_id})
    await session.execute(text("""
        SELECT pv.id FROM product_variants pv
        WHERE pv.id IN (SELECT variant_id FROM order_items WHERE order_id = :oid)
        ORDER BY pv.id FOR NO KEY UPDATE
    """), {"oid": order_id})
