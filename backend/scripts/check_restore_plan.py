"""Verify additive migrations on a restored disposable DB without changing existing records."""
import asyncio
import os
import subprocess
import sys

import asyncpg
from sqlalchemy.engine import make_url

from app.core.config import get_settings

TABLES = {
    "users": "id, role, is_active, auth_version, staff_permissions",
    "orders": "id, order_code, status, payment_status, total_amount, user_id",
    "order_items": "id, order_id, qty, unit_price, line_total",
    "inventory_lots": "id, variant_id, qty_on_hand, qty_reserved, expiry_date, status",
    "lot_allocations": "id, order_item_id, lot_id, qty, status",
    "community_posts": "id, slug, moderation_status, lifecycle_status, title",
    "rescue_animals": "id, code, slug, name, adoption_state, ownership_hold, post_id, version",
    "rescue_episodes": "id, animal_id, location_id, assignee_id, started_at, ended_at, outcome",
    "rescue_funds": "id, title, status",
    "rescue_ledger": "id, fund_id, kind, amount, reference, reverses_id",
    "rescue_supply_receipts": "id, quantity, accepted_quantity, reference",
}


async def main():
    configured = make_url(get_settings().database_url)
    name = sys.argv[1]
    assert name.startswith("pethome_restore_plan_") and name != configured.database
    target = configured.set(database=name)
    async def snapshot():
        connection = await asyncpg.connect(host=target.host, port=target.port or 5432,
            user=target.username, password=target.password, database=name)
        try:
            result = {}
            for table, columns in TABLES.items():
                row = await connection.fetchrow(f"SELECT count(*) AS n, md5(coalesce(string_agg(md5(row_to_json(x)::text), '' ORDER BY id), '')) AS digest FROM (SELECT {columns} FROM {table}) x")
                result[table] = (row["n"], row["digest"])
            return result
        finally:
            await connection.close()
    before = await snapshot()
    env = dict(os.environ, DATABASE_URL=target.render_as_string(hide_password=False))
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, check=True)
    assert before == await snapshot(), "Existing business data changed during migration"
    print("PASS: restored database readable; additive migration preserves users, orders, items, inventory, reservations and rescue posts")
    print("Checked row counts:", {table: counts[0] for table, counts in before.items()})


if __name__ == "__main__":
    asyncio.run(main())
