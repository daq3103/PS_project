from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.deps import require_platform_manager
from app.models.admin_archive import AdminArchive
from app.models.catalog import Category, Product, ProductVariant
from app.models.commerce import Order, Promotion
from app.models.inventory import InventoryLot
from app.models.user import User
from app.modules.admin.archive import visible
from app.modules.inventory.fefo_service import _refresh_variant_cache

router = APIRouter(prefix="/api/v1/admin/records", tags=["admin-archive"])


@router.delete("/{kind}/{record_id}", status_code=204)
async def remove_record(kind: Literal["categories", "products", "lots", "promotions", "orders"], record_id: UUID,
                        user: User = Depends(require_platform_manager), db: AsyncSession = Depends(get_db)):
    if await db.get(AdminArchive, (kind, record_id)):
        return Response(status_code=204)
    model = {"categories": Category, "products": Product, "lots": InventoryLot, "promotions": Promotion, "orders": Order}[kind]
    if kind == "lots":
        existing = await db.get(InventoryLot, record_id)
        if existing:
            await db.execute(select(ProductVariant.id).where(ProductVariant.id == existing.variant_id).with_for_update())
    row = await db.scalar(select(model).where(model.id == record_id).with_for_update().execution_options(populate_existing=True))
    if not row:
        raise HTTPException(404, "Không tìm thấy bản ghi.")
    if await db.get(AdminArchive, (kind, record_id)):
        return Response(status_code=204)
    if kind == "categories":
        if await db.scalar(select(Product.id).where(Product.category_id == record_id, visible(Product.id, "products")).limit(1)):
            raise HTTPException(409, "Danh mục còn sản phẩm. Chuyển hoặc xóa các sản phẩm trước.")
        row.is_active = False
    elif kind == "products":
        row.status = "hidden"
        await db.execute(update(ProductVariant).where(ProductVariant.product_id == record_id).values(is_active=False))
    elif kind == "promotions":
        row.is_active = False
    elif kind == "lots":
        if row.qty_reserved or row.qty_on_hand:
            raise HTTPException(409, "Chỉ xóa lô đã hết hàng và không còn giữ cho đơn. Hãy điều chỉnh tồn hoặc xử lý đơn trước.")
        row.status = "locked"
        await db.flush()
        await _refresh_variant_cache(db, row.variant_id)
    elif kind == "orders" and (row.status != "cancelled" or row.payment_status != "unpaid"):
        raise HTTPException(409, "Chỉ xóa khỏi danh sách đơn đã hủy và chưa thu tiền. Đơn đang xử lý hoặc có thanh toán phải giữ để đối soát.")
    db.add(AdminArchive(resource_kind=kind, resource_id=record_id, actor_user_id=user.id))
    await db.commit()
    return Response(status_code=204)
