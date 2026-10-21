"""Import inventory lots from CSV with dry-run / apply.

CSV columns (header required):
  variant_id,lot_no,qty,unit_cost,expiry_date,manufactured_date,note

Usage:
  python scripts/import_lots_csv.py path/to/lots.csv --dry-run
  python scripts/import_lots_csv.py path/to/lots.csv --apply

Run inside fastapi-api container so DATABASE_URL and app package resolve.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

_SCRIPT = Path(__file__).resolve().parent
if (_SCRIPT.parent / "app").is_dir():
    BACKEND = _SCRIPT.parent  # backend/scripts/...
elif (_SCRIPT.parent / "backend" / "app").is_dir():
    BACKEND = _SCRIPT.parent / "backend"  # repo/scripts/...
else:
    raise SystemExit("Cannot locate backend/app")
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.catalog import ProductVariant
from app.models.inventory import InventoryLot, StockMovement


def parse_date(raw: str | None) -> date | None:
    if not raw or not raw.strip():
        return None
    return datetime.strptime(raw.strip()[:10], "%Y-%m-%d").date()


def load_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"variant_id", "lot_no", "qty", "unit_cost"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise SystemExit(f"CSV must include columns: {sorted(required)}")
        return [dict(r) for r in reader]


async def validate(session: AsyncSession, rows: list[dict]) -> list[str]:
    errors: list[str] = []
    for i, row in enumerate(rows, start=2):
        try:
            vid = UUID(row["variant_id"].strip())
        except Exception:
            errors.append(f"L{i}: invalid variant_id")
            continue
        variant = await session.get(ProductVariant, vid)
        if not variant:
            errors.append(f"L{i}: variant not found {vid}")
        try:
            qty = int(row["qty"])
            if qty <= 0:
                errors.append(f"L{i}: qty must be > 0")
        except ValueError:
            errors.append(f"L{i}: qty not an int")
        try:
            int(row["unit_cost"])
        except ValueError:
            errors.append(f"L{i}: unit_cost not an int")
        lot_no = (row.get("lot_no") or "").strip()
        if not lot_no:
            errors.append(f"L{i}: lot_no empty")
        else:
            exists = await session.scalar(
                select(InventoryLot.id).where(
                    InventoryLot.variant_id == vid,
                    InventoryLot.lot_no == lot_no,
                )
            )
            if exists:
                errors.append(f"L{i}: lot_no already exists for variant ({lot_no})")
        try:
            parse_date(row.get("expiry_date"))
            parse_date(row.get("manufactured_date"))
        except ValueError:
            errors.append(f"L{i}: bad date (use YYYY-MM-DD)")
    return errors


async def apply_rows(session: AsyncSession, rows: list[dict]) -> int:
    created = 0
    for row in rows:
        qty = int(row["qty"])
        lot = InventoryLot(
            variant_id=UUID(row["variant_id"].strip()),
            lot_no=row["lot_no"].strip(),
            manufactured_date=parse_date(row.get("manufactured_date")),
            expiry_date=parse_date(row.get("expiry_date")),
            unit_cost=int(row["unit_cost"]),
            qty_initial=qty,
            qty_on_hand=qty,
            qty_reserved=0,
            status="active",
            note=(row.get("note") or "").strip() or "csv_import",
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
                note="CSV import",
            )
        )
        await session.execute(
            text("""
                UPDATE product_variants
                SET cached_available_qty = cached_available_qty + :q, updated_at = NOW()
                WHERE id = :vid
            """),
            {"q": qty, "vid": lot.variant_id},
        )
        created += 1
    await session.commit()
    return created


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import lots CSV")
    parser.add_argument("csv_path", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not args.csv_path.is_file():
        raise SystemExit(f"File not found: {args.csv_path}")

    rows = load_rows(args.csv_path)
    print(f"ROWS {len(rows)}")

    async with AsyncSessionLocal() as session:
        errors = await validate(session, rows)
        if errors:
            print("VALIDATION_FAILED")
            for e in errors:
                print(e)
            raise SystemExit(1)
        print("VALIDATION_OK")
        if args.dry_run:
            print("DRY_RUN — no writes")
            return
        n = await apply_rows(session, rows)
        print(f"APPLIED {n} lots")


if __name__ == "__main__":
    asyncio.run(main())
