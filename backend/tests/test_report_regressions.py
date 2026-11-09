"""Regressions from PetHome_ket_qua_test.xlsx; no live database or Redis needed."""
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.modules.admin.router import dashboard, drift_report
from app.modules.customer.address_router import AddressCreate, AddressUpdate


@pytest.mark.parametrize("phone", ["abc", "abcdefghij", "09123abc456", "1234567890"])
def test_address_rejects_invalid_phone_on_create_and_edit(phone):
    with pytest.raises(ValidationError) as exc:
        AddressUpdate(recipient_phone=phone)
    assert exc.value.errors()[0]["loc"] == ("recipient_phone",)
    with pytest.raises(ValidationError):
        AddressCreate(
            recipient_name="QA", recipient_phone=phone,
            province_id=1, province_name="Hà Nội", district_id=1, district_name="QA",
            ward_code="1", ward_name="QA", street_address="12 QA",
        )


def test_address_accepts_phone_and_default_only_update():
    assert AddressUpdate(recipient_phone="0901234567").recipient_phone == "0901234567"
    assert AddressUpdate(is_default=True).model_dump(exclude_unset=True) == {"is_default": True}


@pytest.mark.asyncio
async def test_dashboard_and_report_count_only_physical_stock_changes():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE inventory_lots(id TEXT, lot_no TEXT, variant_id TEXT, qty_on_hand INT);
        CREATE TABLE stock_movements(lot_id TEXT, qty_delta INT, reason TEXT);
        INSERT INTO inventory_lots VALUES ('a','SEED-001','v1',10),('b','DRIFT','v2',8),('c','EMPTY','v3',0);
        INSERT INTO stock_movements VALUES ('a',15,'initial_import'),('a',-5,'order_deduct'),('a',5,'order_release'),('b',10,'initial_import');
    """)

    async def execute(sql):
        # SQLite supports this aggregate/join; only the PostgreSQL integer cast differs.
        rows = [dict(r) for r in db.execute(str(sql).replace("::int", ""))]
        return SimpleNamespace(mappings=lambda: SimpleNamespace(first=lambda: rows[0], all=lambda: rows))

    session = SimpleNamespace(
        scalar=AsyncMock(return_value=0),
        scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [])), execute=execute,
    )
    try:
        summary = await dashboard(_staff=None, session=session)
        detail = await drift_report(_staff=None, session=session)
        assert summary.drift_count == detail["drift_count"] == 1
        by_lot = {r["lot_no"]: r for r in detail["lots"]}
        assert by_lot["SEED-001"]["drift"] == 0  # release did not receive five units
        assert by_lot["DRIFT"]["drift"] == -2  # real discrepancy remains visible
        assert by_lot["EMPTY"]["drift"] == 0
    finally:
        db.close()


@pytest.mark.asyncio
async def test_admin_post_list_batches_authors(monkeypatch):
    from app.modules.community import admin_router

    rows = [SimpleNamespace(author_user_id="author1") for _ in range(50)]
    monkeypatch.setattr(admin_router.service, "admin_list_posts", AsyncMock(return_value=(rows, 50)))
    author = SimpleNamespace(id="author1", full_name="QA")
    session = SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [author])))

    async def out(session, post, authors=None):
        return {"author": authors[post.author_user_id].full_name}

    monkeypatch.setattr(admin_router, "admin_out", out)
    result = await admin_router.posts(qs=None, session=session)
    assert len(result) == 50 and result[0]["author"] == "QA"
    assert session.scalars.await_count == 1
