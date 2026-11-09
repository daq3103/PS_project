"""Seven-day Shop overview and private, auditable operating expenses."""
import secrets
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import require_platform_manager, require_warehouse_or_owner
from app.models.shop_expense import ShopExpense, ShopExpenseReceipt
from app.models.user import User
from app.modules.community.upload_service import FORMATS, transform_image

router = APIRouter(prefix="/api/v1/admin", tags=["shop-finance"])
ZONE = ZoneInfo("Asia/Ho_Chi_Minh")


class ExpenseIn(BaseModel):
    spent_on: date
    category: str = Field(pattern="^(shipping|supplies|other)$")
    amount: int = Field(gt=0, le=10_000_000_000)
    note: str = Field(min_length=3, max_length=2000)
    reference: str | None = Field(default=None, max_length=150)


class VoidIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


def expense_data(row: ShopExpense, receipts: list[ShopExpenseReceipt]):
    return {"id": row.id, "spent_on": row.spent_on, "category": row.category,
            "amount": row.amount, "note": row.note, "reference": row.reference,
            "actor_user_id": row.actor_user_id, "created_at": row.created_at,
            "voided_at": row.voided_at, "voided_by": row.voided_by,
            "void_reason": row.void_reason,
            "receipts": [{"id": r.id, "created_at": r.created_at} for r in receipts]}


async def receipts_for(db: AsyncSession, expense_id: UUID):
    return (await db.scalars(select(ShopExpenseReceipt).where(ShopExpenseReceipt.expense_id == expense_id)
                             .order_by(ShopExpenseReceipt.created_at, ShopExpenseReceipt.id))).all()


@router.get("/reports/overview")
async def overview(user: User = Depends(require_warehouse_or_owner), db: AsyncSession = Depends(get_db)):
    today = datetime.now(ZONE).date()
    first = today - timedelta(days=6)
    start = datetime.combine(first, time.min, tzinfo=ZONE)
    end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=ZONE)
    days = {first + timedelta(days=i): {"day": first + timedelta(days=i), "orders": 0,
        "delivered_orders": 0, "revenue": 0, "product_cost": 0, "carrier_shipping_cost": 0,
        "other_expenses": 0, "missing_product_cost_orders": 0, "missing_shipping_cost_orders": 0}
        for i in range(7)}
    placed = (await db.execute(text("""
        SELECT (created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS day, COUNT(*) AS count
        FROM orders WHERE created_at >= :start AND created_at < :end GROUP BY day
    """), {"start": start, "end": end})).mappings().all()
    for row in placed:
        days[row["day"]]["orders"] = int(row["count"])
    delivered = (await db.execute(text("""
        WITH delivery AS (
          SELECT order_id, MIN(created_at) AS delivered_at FROM order_status_history
          WHERE to_status = 'delivered' GROUP BY order_id
        ), cost AS (
          SELECT oi.order_id, SUM(la.qty * la.unit_cost_snapshot) AS product_cost,
                 COUNT(DISTINCT oi.id) FILTER (WHERE la.id IS NOT NULL) AS priced_items
          FROM order_items oi LEFT JOIN lot_allocations la ON la.order_item_id = oi.id
          GROUP BY oi.order_id
        ), item_count AS (
          SELECT order_id, COUNT(*) AS item_count FROM order_items GROUP BY order_id
        ), carrier AS (
          SELECT order_id, SUM(shipping_fee_charged_by_carrier) AS shipping_cost,
                 COUNT(*) FILTER (WHERE shipping_fee_charged_by_carrier IS NULL) AS missing_fee
          FROM fulfillments GROUP BY order_id
        )
        SELECT (delivery.delivered_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS day,
               COUNT(*) AS orders, COALESCE(SUM(o.total_amount),0) AS revenue,
               COALESCE(SUM(cost.product_cost),0) AS product_cost,
               COALESCE(SUM(carrier.shipping_cost),0) AS shipping_cost,
               COUNT(*) FILTER (WHERE COALESCE(cost.priced_items,0) < COALESCE(item_count.item_count,0)) AS missing_product_cost,
               COUNT(*) FILTER (WHERE carrier.order_id IS NULL OR carrier.missing_fee > 0) AS missing_shipping_cost
        FROM delivery JOIN orders o ON o.id = delivery.order_id
        LEFT JOIN cost ON cost.order_id = o.id
        LEFT JOIN item_count ON item_count.order_id = o.id
        LEFT JOIN carrier ON carrier.order_id = o.id
        WHERE delivery.delivered_at >= :start AND delivery.delivered_at < :end AND o.status = 'delivered'
        GROUP BY day
    """), {"start": start, "end": end})).mappings().all()
    for row in delivered:
        day = days[row["day"]]
        day.update(delivered_orders=int(row["orders"]), revenue=int(row["revenue"]),
                   product_cost=int(row["product_cost"]), carrier_shipping_cost=int(row["shipping_cost"]),
                   missing_product_cost_orders=int(row["missing_product_cost"]),
                   missing_shipping_cost_orders=int(row["missing_shipping_cost"]))
    expenses = (await db.execute(text("""
        SELECT spent_on AS day, SUM(amount) AS amount FROM shop_expenses
        WHERE spent_on >= :first AND spent_on <= :today AND voided_at IS NULL GROUP BY spent_on
    """), {"first": first, "today": today})).mappings().all()
    for row in expenses:
        days[row["day"]]["other_expenses"] = int(row["amount"])
    for day in days.values():
        day["estimated_profit"] = day["revenue"] - day["product_cost"] - day["carrier_shipping_cost"] - day["other_expenses"]
    statuses = (await db.execute(text("""
        SELECT status, COUNT(*) AS count FROM orders
        WHERE created_at >= :start AND created_at < :end GROUP BY status
    """), {"start": start, "end": end})).mappings().all()
    completed = sum(int(r["count"]) for r in statuses if r["status"] == "delivered")
    cancelled = sum(int(r["count"]) for r in statuses if r["status"] in ("cancelled", "returned"))
    total = sum(int(r["count"]) for r in statuses)
    return {"date_from": first, "date_to": today, "daily": list(days.values()),
            "orders_by_progress": {"completed": completed, "pending": total - completed - cancelled,
                                   "cancelled_or_returned": cancelled},
            "basis": "Đơn đặt trong 7 ngày; doanh thu và giá vốn ghi vào ngày giao thành công. Lãi trừ giá vốn, phí hãng đã ghi và chi phí Shop đã nhập; chưa trừ phí chưa có dữ liệu."}


@router.get("/shop-expenses")
async def list_expenses(user: User = Depends(require_warehouse_or_owner), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(ShopExpense).order_by(ShopExpense.spent_on.desc(), ShopExpense.created_at.desc()).limit(100))).all()
    names = {person.id: person.full_name for person in (await db.scalars(
        select(User).where(User.id.in_({row.actor_user_id for row in rows} | {row.voided_by for row in rows if row.voided_by}))
    )).all()} if rows else {}
    result = []
    for row in rows:
        item = expense_data(row, await receipts_for(db, row.id))
        item["actor_name"] = names.get(row.actor_user_id, "Nhân viên")
        item["voided_by_name"] = names.get(row.voided_by) if row.voided_by else None
        result.append(item)
    return result


@router.post("/shop-expenses", status_code=201)
async def create_expense(body: ExpenseIn, user: User = Depends(require_platform_manager), db: AsyncSession = Depends(get_db)):
    if not body.note.strip() or body.spent_on > datetime.now(ZONE).date():
        raise HTTPException(422, "Cần ghi chú khoản chi và chọn ngày không ở tương lai.")
    row = ShopExpense(**{**body.model_dump(), "note": body.note.strip()}, actor_user_id=user.id)
    db.add(row)
    await db.flush()
    result = {**expense_data(row, []), "actor_name": user.full_name}
    await db.commit()
    return result


@router.post("/shop-expenses/{expense_id}/receipts", status_code=201)
async def add_receipt(expense_id: UUID, file: UploadFile = File(),
                      user: User = Depends(require_platform_manager), db: AsyncSession = Depends(get_db)):
    expense = await db.get(ShopExpense, expense_id)
    if not expense or expense.voided_at:
        raise HTTPException(404, "Không tìm thấy khoản chi đang có hiệu lực.")
    if len(await receipts_for(db, expense_id)) >= 5:
        raise HTTPException(409, "Mỗi khoản chi nhận tối đa 5 ảnh.")
    maximum = get_settings().max_community_upload_bytes
    raw = await file.read(maximum + 1)
    if len(raw) > maximum:
        raise HTTPException(413, "Ảnh vượt quá 5 MB.")
    if file.content_type not in FORMATS:
        raise HTTPException(422, "Chỉ nhận ảnh JPEG, PNG hoặc WebP.")
    clean, _, _ = await run_in_threadpool(transform_image, raw, file.content_type)
    key = secrets.token_urlsafe(24) + ".jpg"
    folder = Path(get_settings().community_upload_dir) / "shop-expenses"
    await run_in_threadpool(folder.mkdir, parents=True, exist_ok=True)
    path = folder / key
    await run_in_threadpool(path.write_bytes, clean)
    receipt = ShopExpenseReceipt(expense_id=expense_id, storage_key=key, uploader_user_id=user.id)
    db.add(receipt)
    try:
        await db.flush()
        result = {"id": receipt.id, "created_at": receipt.created_at}
        await db.commit()
    except Exception:
        await run_in_threadpool(path.unlink, missing_ok=True)
        raise
    return result


@router.get("/shop-expenses/{expense_id}/receipts/{receipt_id}")
async def get_receipt(expense_id: UUID, receipt_id: UUID,
                      user: User = Depends(require_warehouse_or_owner), db: AsyncSession = Depends(get_db)):
    receipt = await db.get(ShopExpenseReceipt, receipt_id)
    if not receipt or receipt.expense_id != expense_id:
        raise HTTPException(404, "Không tìm thấy chứng từ.")
    path = Path(get_settings().community_upload_dir) / "shop-expenses" / receipt.storage_key
    if not path.is_file():
        raise HTTPException(404, "Ảnh chứng từ không còn trong kho lưu trữ.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})


@router.post("/shop-expenses/{expense_id}/void")
async def void_expense(expense_id: UUID, body: VoidIn,
                       user: User = Depends(require_platform_manager), db: AsyncSession = Depends(get_db)):
    row = await db.scalar(select(ShopExpense).where(ShopExpense.id == expense_id).with_for_update())
    if not row:
        raise HTTPException(404, "Không tìm thấy khoản chi.")
    if row.voided_at:
        raise HTTPException(409, "Khoản chi đã được hủy ghi nhận.")
    if len(body.reason.strip()) < 5:
        raise HTTPException(422, "Lý do hủy cần ít nhất 5 ký tự.")
    row.voided_at = datetime.now(UTC)
    row.voided_by = user.id
    row.void_reason = body.reason.strip()
    await db.commit()
    return expense_data(row, await receipts_for(db, expense_id))
