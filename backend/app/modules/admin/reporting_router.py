from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.deps import require_warehouse_or_owner
from app.models.catalog import Product, ProductVariant
from app.models.user import User

router = APIRouter(prefix="/api/v1/admin", tags=["sales-reporting"])


@router.get("/stock-alerts")
async def stock_alerts(user: User = Depends(require_warehouse_or_owner), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(ProductVariant, Product.name).join(Product, Product.id == ProductVariant.product_id)
        .where(ProductVariant.is_active.is_(True), ProductVariant.cached_available_qty <= ProductVariant.low_stock_threshold)
        .order_by(ProductVariant.cached_available_qty, Product.name, ProductVariant.title))).all()
    return [{"id": v.id, "product_name": name, "title": v.title, "sku": v.sku, "quantity": v.cached_available_qty,
             "threshold": v.low_stock_threshold} for v, name in rows]


@router.get("/reports/sales")
async def sales_report(date_from: date | None = None, date_to: date | None = None,
                       user: User = Depends(require_warehouse_or_owner), db: AsyncSession = Depends(get_db)):
    zone = ZoneInfo("Asia/Ho_Chi_Minh")
    last = date_to or datetime.now(zone).date()
    first = date_from or last - timedelta(days=29)
    if first > last:
        raise HTTPException(422, "Ngày bắt đầu không được sau ngày kết thúc.")
    params = {"start": datetime.combine(first, time.min, tzinfo=zone), "end": datetime.combine(last + timedelta(days=1), time.min, tzinfo=zone)}
    rows = (await db.execute(text("""
        SELECT status, COUNT(*) AS orders, COALESCE(SUM(total_amount),0) AS amount,
               COALESCE(SUM(discount_amount),0) AS discount,
               COALESCE(SUM(CASE WHEN payment_status IN ('paid','overpaid') THEN total_amount ELSE 0 END),0) AS paid_value
        FROM orders WHERE created_at >= :start AND created_at < :end GROUP BY status ORDER BY status
    """), params)).mappings().all()
    daily = (await db.execute(text("""
        SELECT (created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS day, COUNT(*) AS orders,
               COALESCE(SUM(CASE WHEN status = 'delivered' THEN total_amount ELSE 0 END),0) AS delivered_value,
               COUNT(*) FILTER (WHERE status = 'delivered') AS delivered_orders,
               COUNT(*) FILTER (WHERE status IN ('cancelled', 'returned')) AS closed_orders,
               COUNT(*) FILTER (WHERE status NOT IN ('delivered', 'cancelled', 'returned')) AS processing_orders,
               COUNT(*) FILTER (WHERE status = 'delivered' AND payment_method = 'cod'
                   AND payment_status NOT IN ('paid', 'overpaid')) AS cod_pending_orders
        FROM orders WHERE created_at >= :start AND created_at < :end GROUP BY day ORDER BY day
    """), params)).mappings().all()
    daily_statuses = (await db.execute(text("""
        SELECT (created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS day,
               status, COUNT(*) AS orders
        FROM orders WHERE created_at >= :start AND created_at < :end
        GROUP BY day, status ORDER BY day, status
    """), params)).mappings().all()
    status_by_day: dict[date, list[dict]] = {}
    for row in daily_statuses:
        status_by_day.setdefault(row["day"], []).append({"status": row["status"], "orders": int(row["orders"])})
    statuses = [{"status": r["status"], "orders": int(r["orders"]), "amount": int(r["amount"])} for r in rows]
    return {"date_from": first, "date_to": last, "orders": sum(int(r["orders"]) for r in rows),
        "cancelled_orders": sum(int(r["orders"]) for r in rows if r["status"] == "cancelled"),
        "ordered_value": sum(int(r["amount"]) for r in rows if r["status"] != "cancelled"),
        "delivered_value": sum(int(r["amount"]) for r in rows if r["status"] == "delivered"),
        "paid_order_value": sum(int(r["paid_value"]) for r in rows if r["status"] != "cancelled"),
        "discount": sum(int(r["discount"]) for r in rows if r["status"] != "cancelled"),
        "statuses": statuses, "daily": [{**dict(r), "handled": int(r["processing_orders"]) + int(r["cod_pending_orders"]) == 0,
            "status_breakdown": status_by_day.get(r["day"], [])} for r in daily]}
