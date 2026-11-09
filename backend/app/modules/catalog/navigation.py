"""Editable Shop menu. Category names and paths always come from the catalog."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_platform_manager, require_shop_staff
from app.models.catalog import Category
from app.models.navigation import ShopNavigationSettings
from app.models.user import User

router = APIRouter(prefix="/api/v1", tags=["catalog"])

FIXED = {
    "shop": ("Khám phá shop", "/shop"),
    "search": ("Tìm sản phẩm", "/search"),
    "track": ("Tra cứu đơn hàng", "/track-order"),
}


class NavigationItem(BaseModel):
    key: str = Field(min_length=1, max_length=60)
    label: str = Field(min_length=1, max_length=60)
    href: str = Field(min_length=1, max_length=300)
    visible: bool = True


class NavigationUpdate(BaseModel):
    items: list[NavigationItem] = Field(min_length=3, max_length=30)


def internal_href(href: str) -> bool:
    return (
        href.startswith("/") and not href.startswith("//")
        and "\\" not in href and not any(ord(char) < 32 for char in href)
    )


async def current_items(db: AsyncSession) -> list[NavigationItem]:
    categories = (await db.scalars(select(Category).where(Category.is_active.is_(True)).order_by(Category.sort_order, Category.name))).all()
    saved = await db.get(ShopNavigationSettings, 1)
    defaults = [NavigationItem(key=key, label=label, href=href) for key, (label, href) in FIXED.items()]
    category_items = [NavigationItem(key=f"category:{category.id}", label=category.name,
                                     href=f"/c/{category.slug}", visible=category.show_in_nav) for category in categories]
    if not saved:
        return defaults[:2] + [item for item in category_items if item.visible] + [defaults[2]] + [item for item in category_items if not item.visible]

    by_key = {item.key: item for item in defaults + category_items}
    output: list[NavigationItem] = []
    for raw in saved.items:
        key = raw.get("key")
        if key in by_key:
            item = by_key.pop(key)
            if key in FIXED:
                item.visible = bool(raw.get("visible", True))
            output.append(item)
        elif isinstance(key, str) and key.startswith("custom:") and internal_href(str(raw.get("href", ""))):
            output.append(NavigationItem.model_validate(raw))
    # Newly created categories appear in the editor without disturbing saved order.
    output.extend(by_key.values())
    return output


@router.get("/shop/navigation", response_model=list[NavigationItem])
async def public_navigation(db: AsyncSession = Depends(get_db)):
    return [item for item in await current_items(db) if item.visible]


@router.get("/admin/shop/navigation", response_model=list[NavigationItem])
async def admin_navigation(
    _staff: User = Depends(require_shop_staff), db: AsyncSession = Depends(get_db)
):
    return await current_items(db)


@router.put("/admin/shop/navigation", response_model=list[NavigationItem])
async def save_navigation(
    body: NavigationUpdate,
    _staff: User = Depends(require_platform_manager),
    db: AsyncSession = Depends(get_db),
):
    categories = (await db.scalars(select(Category).where(Category.is_active.is_(True)))).all()
    by_key = {f"category:{category.id}": category for category in categories}
    keys = [item.key for item in body.items]
    if len(keys) != len(set(keys)) or not set(FIXED).issubset(keys):
        raise HTTPException(422, "Menu có mục trùng hoặc thiếu mục mặc định.")
    normalized = []
    for item in body.items:
        if item.key in FIXED:
            label, href = FIXED[item.key]
            normalized.append(NavigationItem(key=item.key, label=label, href=href, visible=item.visible))
        elif item.key in by_key:
            category = by_key[item.key]
            category.show_in_nav = item.visible
            normalized.append(NavigationItem(key=item.key, label=category.name,
                                             href=f"/c/{category.slug}", visible=item.visible))
        elif item.key.startswith("custom:"):
            try:
                UUID(item.key.removeprefix("custom:"))
            except ValueError:
                raise HTTPException(422, "Mã mục menu không hợp lệ.") from None
            if not internal_href(item.href):
                raise HTTPException(422, "Liên kết cần là đường dẫn nội bộ bắt đầu bằng /.")
            if not item.label.strip():
                raise HTTPException(422, "Cần nhập tên hiển thị cho mục menu.")
            normalized.append(NavigationItem(key=item.key, label=item.label.strip(), href=item.href, visible=item.visible))
        else:
            raise HTTPException(422, "Danh mục trong menu không tồn tại hoặc đã tắt.")
    row = await db.get(ShopNavigationSettings, 1)
    if row:
        row.items = [item.model_dump() for item in normalized]
    else:
        db.add(ShopNavigationSettings(id=1, items=[item.model_dump() for item in normalized]))
    await db.commit()
    return await current_items(db)
