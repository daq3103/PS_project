"""Staff admin API (orders, inventory, promotions, reviews, reports, TOTP)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import pyotp
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_owner, require_staff_user
from app.core.encryption import encrypt_secret
from app.models.catalog import Product, ProductVariant, Review
from app.models.commerce import Order, OrderStatusHistory, Promotion
from app.models.fulfillment import Fulfillment
from app.models.inventory import InventoryLot, StockMovement
from app.models.user import User
from app.modules.inventory.fefo_service import deduct_on_pack
from app.modules.order.schemas import OrderOut
from app.modules.order.state import transition_order
from app.worker import enqueue as job_enqueue

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class TotpEnrollOut(BaseModel):
    secret: str
    provisioning_uri: str
    message: str = "Scan with authenticator app, then POST /totp/verify"


class TotpVerifyIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class StockAdjustIn(BaseModel):
    lot_id: UUID
    qty_delta: int
    reason: str = Field(
        ...,
        pattern="^(stocktake_adjust|damaged_adjust|manual_correct)$",
    )
    note: str | None = None

    @field_validator("qty_delta")
    @classmethod
    def _qty_delta_nonzero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("qty_delta phải khác 0")
        return value


class LotCreateIn(BaseModel):
    variant_id: UUID
    lot_no: str
    qty: int = Field(gt=0)
    unit_cost: int = Field(ge=0)
    expiry_date: date | None = None
    manufactured_date: date | None = None
    note: str | None = None


class PromotionCreateIn(BaseModel):
    code: str
    description: str | None = None
    discount_type: str = Field(pattern="^(percentage|fixed_amount|free_shipping)$")
    discount_value: int = Field(gt=0)
    max_discount_amount: int | None = None
    min_order_subtotal: int = 0
    usage_limit: int | None = None
    usage_limit_per_user: int | None = 1
    starts_at: datetime
    expires_at: datetime


class OrderListOut(BaseModel):
    id: UUID
    order_code: str
    status: str
    payment_method: str
    payment_status: str
    total_amount: int
    customer_name: str
    customer_phone: str
    created_at: datetime
    tracking_code: str | None = None
    label_print_url: str | None = None
    package_count: int | None = None
    total_weight_grams: int | None = None

    model_config = {"from_attributes": True}


class CreateShipmentIn(BaseModel):
    carrier_code: str = Field(default="mock_ghn")
    package_count: int = Field(default=1, ge=1, le=10)
    total_weight_grams: int | None = Field(default=None, ge=1)


class OrderFulfillmentOut(BaseModel):
    carrier_code: str
    tracking_code: str | None = None
    label_print_url: str | None = None
    package_count: int
    total_weight_grams: int
    internal_status: str
    cod_reconciled: bool

    model_config = {"from_attributes": True}


class OrderStatusHistoryOut(BaseModel):
    id: UUID
    from_status: str | None = None
    to_status: str
    actor_type: str
    actor_user_id: UUID | None = None
    note: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderDetailOut(OrderOut):
    status_history: list[OrderStatusHistoryOut] = []
    fulfillment: OrderFulfillmentOut | None = None

    model_config = {"from_attributes": True}


class StockMovementOut(BaseModel):
    id: UUID
    lot_id: UUID
    variant_id: UUID
    lot_no: str
    qty_delta: int
    reason: str
    ref_type: str | None = None
    ref_id: UUID | None = None
    actor_user_id: UUID | None = None
    note: str | None = None
    created_at: datetime


class PromotionUpdateIn(BaseModel):
    is_active: bool | None = None
    usage_limit: int | None = Field(default=None, ge=1)
    starts_at: datetime | None = None
    expires_at: datetime | None = None


class ReviewApproveIn(BaseModel):
    approve: bool = True


@router.post("/totp/enroll", response_model=TotpEnrollOut)
async def totp_enroll(
    user: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> TotpEnrollOut:
    if user.totp_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="TOTP already enabled")
    secret = pyotp.random_base32()
    user.totp_secret_encrypted = encrypt_secret(secret)
    await session.flush()
    totp = pyotp.TOTP(secret)
    label = user.email or user.phone or str(user.id)
    uri = totp.provisioning_uri(name=label, issuer_name="Petshop Admin")
    return TotpEnrollOut(secret=secret, provisioning_uri=uri)


@router.post("/totp/verify")
async def totp_verify(
    body: TotpVerifyIn,
    user: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    if not user.totp_secret_encrypted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Enroll TOTP first")
    from app.core.encryption import decrypt_secret_str

    secret = decrypt_secret_str(user.totp_secret_encrypted)
    totp = pyotp.TOTP(secret)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid code")
    user.totp_enabled = True
    await session.flush()
    return {"totp_enabled": True}


class DashboardKpiOut(BaseModel):
    orders_today: int
    revenue_today: int
    pending_orders: int
    pending_reviews: int
    drift_count: int
    out_of_stock_variants: int
    low_stock_variants: int
    lots_expiring_30d: int
    recent_orders: list[OrderListOut]


@router.get("/dashboard", response_model=DashboardKpiOut)
async def dashboard(
    _staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> DashboardKpiOut:
    today = datetime.now(UTC).date()
    today_start = datetime.combine(today, datetime.min.time(), tzinfo=UTC)

    orders_today = await session.scalar(
        select(func.count()).where(Order.created_at >= today_start)
    )
    revenue_today = await session.scalar(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.created_at >= today_start,
            Order.status != "cancelled",
        )
    )
    pending_orders = await session.scalar(
        select(func.count()).where(Order.status == "pending")
    )
    pending_reviews = await session.scalar(
        select(func.count()).where(Review.is_approved.is_(False))
    )
    out_of_stock = await session.scalar(
        select(func.count()).where(
            ProductVariant.is_active.is_(True),
            ProductVariant.cached_available_qty == 0,
        )
    )
    low_stock = await session.scalar(
        select(func.count()).where(
            ProductVariant.is_active.is_(True),
            ProductVariant.cached_available_qty > 0,
            ProductVariant.cached_available_qty <= ProductVariant.low_stock_threshold,
        )
    )
    expiry_cutoff = date.today() + timedelta(days=30)
    lots_expiring = await session.scalar(
        select(func.count()).where(
            InventoryLot.status == "active",
            InventoryLot.expiry_date.isnot(None),
            InventoryLot.expiry_date <= expiry_cutoff,
        )
    )

    # drift count
    drift_rows = (
        await session.execute(
            text("""
                SELECT COUNT(*) AS drift_count FROM (
                    SELECT il.id, il.qty_on_hand, COALESCE(SUM(sm.qty_delta), 0) AS movements_sum
                    FROM inventory_lots il
                    LEFT JOIN stock_movements sm ON sm.lot_id = il.id
                    GROUP BY il.id, il.qty_on_hand
                ) t
                WHERE qty_on_hand != movements_sum
            """)
        )
    ).mappings().first()
    drift_count = int(drift_rows["drift_count"]) if drift_rows else 0

    recent_rows = (await session.scalars(
        select(Order).order_by(Order.created_at.desc()).limit(5)
    )).all()
    recent: list[OrderListOut] = []
    for o in recent_rows:
        ff = await session.scalar(
            select(Fulfillment)
            .where(Fulfillment.order_id == o.id)
            .order_by(Fulfillment.attempt_no.desc())
            .limit(1)
        )
        base = OrderListOut.model_validate(o)
        if ff:
            base.tracking_code = ff.tracking_code
            base.label_print_url = ff.label_print_url
            base.package_count = ff.package_count
            base.total_weight_grams = ff.total_weight_grams
        recent.append(base)

    return DashboardKpiOut(
        orders_today=orders_today or 0,
        revenue_today=revenue_today or 0,
        pending_orders=pending_orders or 0,
        pending_reviews=pending_reviews or 0,
        drift_count=drift_count,
        out_of_stock_variants=out_of_stock or 0,
        low_stock_variants=low_stock or 0,
        lots_expiring_30d=lots_expiring or 0,
        recent_orders=recent,
    )


@router.get("/orders", response_model=list[OrderListOut])
async def list_orders(
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=100),
    payment_method: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    _staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> list[OrderListOut]:
    stmt = select(Order).order_by(Order.created_at.desc())
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    if q:
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            (Order.order_code.ilike(term))
            | (Order.customer_phone.ilike(term))
            | (Order.customer_name.ilike(term))
        )
    if payment_method:
        stmt = stmt.where(Order.payment_method == payment_method)
    if date_from:
        stmt = stmt.where(Order.created_at >= datetime.combine(date_from, datetime.min.time(), tzinfo=UTC))
    if date_to:
        stmt = stmt.where(Order.created_at < datetime.combine(date_to, datetime.max.time(), tzinfo=UTC))
    stmt = stmt.offset(offset).limit(limit)
    rows = (await session.scalars(stmt)).all()
    out: list[OrderListOut] = []
    for o in rows:
        ff = await session.scalar(
            select(Fulfillment)
            .where(Fulfillment.order_id == o.id)
            .order_by(Fulfillment.attempt_no.desc())
            .limit(1)
        )
        base = OrderListOut.model_validate(o)
        if ff:
            base.tracking_code = ff.tracking_code
            base.label_print_url = ff.label_print_url
            base.package_count = ff.package_count
            base.total_weight_grams = ff.total_weight_grams
        out.append(base)
    return out


@router.get("/orders/{order_id}", response_model=OrderDetailOut)
async def get_order_detail(
    order_id: UUID,
    _staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> OrderDetailOut:
    order = await session.get(Order, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Đơn không tồn tại")
    from app.models.commerce import OrderItem

    items = (await session.scalars(select(OrderItem).where(OrderItem.order_id == order_id))).all()
    history = (
        await session.scalars(
            select(OrderStatusHistory)
            .where(OrderStatusHistory.order_id == order_id)
            .order_by(OrderStatusHistory.created_at.desc())
        )
    ).all()
    ff = await session.scalar(
        select(Fulfillment)
        .where(Fulfillment.order_id == order_id)
        .order_by(Fulfillment.attempt_no.desc())
        .limit(1)
    )
    base = OrderOut.from_order(order, list(items))
    detail = OrderDetailOut(**base.model_dump())
    detail.status_history = [OrderStatusHistoryOut.model_validate(h) for h in history]
    if ff:
        detail.fulfillment = OrderFulfillmentOut.model_validate(ff)
    return detail


@router.post("/orders/{order_id}/pack", response_model=OrderOut)
async def pack_order(
    order_id: UUID,
    staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> OrderOut:
    order = await session.get(Order, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Đơn không tồn tại")
    await transition_order(
        session,
        order_id,
        from_status="confirmed",
        to_status="packed",
        actor_type="staff",
        actor_user_id=staff.id,
    )
    await deduct_on_pack(session, order_id)
    await session.refresh(order)
    from app.models.commerce import OrderItem

    items = (await session.scalars(select(OrderItem).where(OrderItem.order_id == order_id))).all()
    return OrderOut.from_order(order, list(items))


@router.post("/orders/{order_id}/ship", response_model=OrderOut)
async def ship_order(
    order_id: UUID,
    staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> OrderOut:
    order = await session.get(Order, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Đơn không tồn tại")
    await transition_order(
        session,
        order_id,
        from_status="packed",
        to_status="shipped",
        actor_type="staff",
        actor_user_id=staff.id,
    )
    from app.models.commerce import OrderItem

    items = (await session.scalars(select(OrderItem).where(OrderItem.order_id == order_id))).all()
    return OrderOut.from_order(order, list(items))


@router.post("/orders/{order_id}/shipments", status_code=status.HTTP_202_ACCEPTED)
async def create_shipment(
    order_id: UUID,
    body: CreateShipmentIn,
    background_tasks: BackgroundTasks,
    _staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    order = await session.get(Order, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Đơn không tồn tại")
    if order.status not in ("confirmed", "packed", "shipped"):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Đơn chưa sẵn sàng tạo vận đơn")
    background_tasks.add_task(
        job_enqueue.enqueue_create_shipment,
        order_id,
        body.carrier_code,
        body.package_count,
        body.total_weight_grams,
    )
    return {"status": "enqueued", "order_id": str(order_id)}


@router.get("/lots")
async def list_lots(
    variant_id: UUID | None = None,
    _staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    stmt = select(InventoryLot).order_by(InventoryLot.expiry_date.asc().nulls_last())
    if variant_id:
        stmt = stmt.where(InventoryLot.variant_id == variant_id)
    lots = (await session.scalars(stmt)).all()
    return [
        {
            "id": str(lot.id),
            "variant_id": str(lot.variant_id),
            "lot_no": lot.lot_no,
            "qty_on_hand": lot.qty_on_hand,
            "qty_reserved": lot.qty_reserved,
            "available": lot.qty_on_hand - lot.qty_reserved,
            "expiry_date": lot.expiry_date.isoformat() if lot.expiry_date else None,
            "status": lot.status,
        }
        for lot in lots
    ]


@router.post("/lots", status_code=status.HTTP_201_CREATED)
async def create_lot(
    body: LotCreateIn,
    staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    variant = await session.get(ProductVariant, body.variant_id)
    if not variant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Variant not found")

    lot = InventoryLot(
        variant_id=body.variant_id,
        lot_no=body.lot_no,
        manufactured_date=body.manufactured_date,
        expiry_date=body.expiry_date,
        unit_cost=body.unit_cost,
        qty_initial=body.qty,
        qty_on_hand=body.qty,
        qty_reserved=0,
        status="active",
        note=body.note,
    )
    session.add(lot)
    await session.flush()

    session.add(
        StockMovement(
            lot_id=lot.id,
            qty_delta=body.qty,
            reason="lot_import",
            ref_type="lot",
            ref_id=lot.id,
            actor_user_id=staff.id,
            note=body.note or "Lot import",
        )
    )
    await session.execute(
        text("""
            UPDATE product_variants
            SET cached_available_qty = cached_available_qty + :q, updated_at = NOW()
            WHERE id = :vid
        """),
        {"q": body.qty, "vid": body.variant_id},
    )
    return {"id": str(lot.id), "lot_no": lot.lot_no}


@router.get("/stock-movements", response_model=list[StockMovementOut])
async def list_stock_movements(
    lot_id: UUID | None = Query(default=None),
    variant_id: UUID | None = Query(default=None),
    reason: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    _staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> list[StockMovementOut]:
    sql = """
        SELECT
            sm.id,
            sm.lot_id,
            il.variant_id,
            il.lot_no,
            sm.qty_delta,
            sm.reason,
            sm.ref_type,
            sm.ref_id,
            sm.actor_user_id,
            sm.note,
            sm.created_at
        FROM stock_movements sm
        JOIN inventory_lots il ON il.id = sm.lot_id
        WHERE 1=1
    """
    params: dict[str, Any] = {}
    if lot_id:
        sql += " AND sm.lot_id = :lot_id"
        params["lot_id"] = lot_id
    if variant_id:
        sql += " AND il.variant_id = :variant_id"
        params["variant_id"] = variant_id
    if reason:
        sql += " AND sm.reason = :reason"
        params["reason"] = reason
    if date_from:
        sql += " AND sm.created_at >= :date_from"
        params["date_from"] = datetime.combine(date_from, datetime.min.time(), tzinfo=UTC)
    if date_to:
        sql += " AND sm.created_at <= :date_to"
        params["date_to"] = datetime.combine(date_to, datetime.max.time(), tzinfo=UTC)
    sql += " ORDER BY sm.created_at DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    rows = (await session.execute(text(sql), params)).mappings().all()
    return [
        StockMovementOut(
            id=r["id"],
            lot_id=r["lot_id"],
            variant_id=r["variant_id"],
            lot_no=r["lot_no"],
            qty_delta=r["qty_delta"],
            reason=r["reason"],
            ref_type=r["ref_type"],
            ref_id=r["ref_id"],
            actor_user_id=r["actor_user_id"],
            note=r["note"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


@router.post("/stock/adjust")
async def adjust_stock(
    body: StockAdjustIn,
    staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    lot = await session.get(InventoryLot, body.lot_id)
    if not lot:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lot not found")

    new_on_hand = lot.qty_on_hand + body.qty_delta
    if new_on_hand < lot.qty_reserved:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Would go below reserved qty")
    if new_on_hand < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid adjustment")

    lot.qty_on_hand = new_on_hand
    session.add(
        StockMovement(
            lot_id=lot.id,
            qty_delta=body.qty_delta,
            reason=body.reason,
            ref_type="adjustment",
            actor_user_id=staff.id,
            note=body.note,
        )
    )
    await session.execute(
        text("""
            UPDATE product_variants pv
            SET cached_available_qty = COALESCE((
                SELECT SUM(GREATEST(0, il.qty_on_hand - il.qty_reserved))
                FROM inventory_lots il
                WHERE il.variant_id = pv.id AND il.status = 'active'
            ), 0),
            updated_at = NOW()
            WHERE pv.id = :vid
        """),
        {"vid": lot.variant_id},
    )
    return {"status": "ok", "lot_id": str(lot.id)}


@router.get("/promotions", response_model=list[dict])
async def list_promotions(
    _staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    promos = (await session.scalars(select(Promotion).order_by(Promotion.created_at.desc()))).all()
    return [
        {
            "id": str(p.id),
            "code": p.code,
            "description": p.description,
            "discount_type": p.discount_type,
            "discount_value": p.discount_value,
            "used_count": p.used_count,
            "usage_limit": p.usage_limit,
            "is_active": p.is_active,
            "starts_at": p.starts_at.isoformat(),
            "expires_at": p.expires_at.isoformat(),
        }
        for p in promos
    ]


@router.post("/promotions", status_code=status.HTTP_201_CREATED)
async def create_promotion(
    body: PromotionCreateIn,
    _owner: User = Depends(require_owner),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    promo = Promotion(
        code=body.code.upper().strip(),
        description=body.description,
        discount_type=body.discount_type,
        discount_value=body.discount_value,
        max_discount_amount=body.max_discount_amount,
        min_order_subtotal=body.min_order_subtotal,
        usage_limit=body.usage_limit,
        usage_limit_per_user=body.usage_limit_per_user,
        starts_at=body.starts_at,
        expires_at=body.expires_at,
        is_active=True,
    )
    session.add(promo)
    await session.flush()
    return {"id": str(promo.id), "code": promo.code}


@router.patch("/promotions/{promotion_id}")
async def update_promotion(
    promotion_id: UUID,
    body: PromotionUpdateIn,
    _owner: User = Depends(require_owner),
    session: AsyncSession = Depends(get_db),
) -> dict:
    promo = await session.get(Promotion, promotion_id)
    if not promo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Promotion not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(promo, k, v)
    await session.flush()
    return {
        "id": str(promo.id),
        "code": promo.code,
        "is_active": promo.is_active,
        "starts_at": promo.starts_at.isoformat(),
        "expires_at": promo.expires_at.isoformat(),
    }


@router.get("/reviews")
async def list_reviews(
    pending_only: bool = Query(default=False),
    _staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    stmt = (
        select(Review, Product.name)
        .outerjoin(Product, Product.id == Review.product_id)
        .order_by(Review.created_at.desc())
        .limit(100)
    )
    if pending_only:
        stmt = stmt.where(Review.is_approved.is_(False))
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": str(r.id),
            "product_id": str(r.product_id),
            "product_name": pname,
            "reviewer_name": r.reviewer_name,
            "rating": r.rating,
            "content": r.content,
            "is_approved": r.is_approved,
            "created_at": r.created_at.isoformat(),
        }
        for r, pname in rows
    ]


@router.post("/reviews/{review_id}/approve")
async def approve_review(
    review_id: UUID,
    body: ReviewApproveIn,
    staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    review = await session.get(Review, review_id)
    if not review:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Review not found")
    if not body.approve:
        await session.delete(review)
        await session.flush()
        return {"id": str(review_id), "is_approved": False, "deleted": True}
    review.is_approved = True
    review.approved_by = staff.id
    await session.flush()
    return {"id": str(review.id), "is_approved": True}


@router.get("/reports/drift")
async def drift_report(
    _staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Compare Σ stock_movements vs inventory_lots.qty_on_hand per lot."""
    rows = (
        await session.execute(
            text("""
                SELECT * FROM (
                    SELECT
                        il.id AS lot_id,
                        il.lot_no,
                        il.variant_id,
                        il.qty_on_hand,
                        COALESCE(SUM(sm.qty_delta), 0)::int AS movements_sum
                    FROM inventory_lots il
                    LEFT JOIN stock_movements sm ON sm.lot_id = il.id
                    GROUP BY il.id, il.lot_no, il.variant_id, il.qty_on_hand
                ) t
                ORDER BY ABS(qty_on_hand - movements_sum) DESC, lot_no
            """)
        )
    ).mappings().all()

    lots = []
    drift_count = 0
    for r in rows:
        drift = int(r["qty_on_hand"]) - int(r["movements_sum"])
        if drift != 0:
            drift_count += 1
        lots.append(
            {
                "lot_id": str(r["lot_id"]),
                "lot_no": r["lot_no"],
                "variant_id": str(r["variant_id"]),
                "qty_on_hand": int(r["qty_on_hand"]),
                "movements_sum": int(r["movements_sum"]),
                "drift": drift,
            }
        )
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "lot_count": len(lots),
        "drift_count": drift_count,
        "lots": lots,
    }
