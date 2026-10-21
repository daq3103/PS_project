from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_staff_user
from app.models.user import User
from app.modules.catalog import service
from app.modules.catalog.schemas import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    ProductCreate,
    ProductImageOut,
    ProductImageUpdateIn,
    ProductOut,
    ProductUpdate,
    VariantCreate,
    VariantOut,
    VariantUpdate,
)

router = APIRouter(prefix="/api/v1", tags=["catalog"])


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    active_only: bool = False,
    session: AsyncSession = Depends(get_db),
) -> list[CategoryOut]:
    cats = await service.list_categories(session, active_only=active_only)
    return [CategoryOut.model_validate(c) for c in cats]


@router.get("/categories/by-slug/{slug}", response_model=CategoryOut)
async def get_category_by_slug(
    slug: str,
    session: AsyncSession = Depends(get_db),
) -> CategoryOut:
    cat = await service.get_category_by_slug(session, slug)
    return CategoryOut.model_validate(cat)


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    body: CategoryCreate,
    _staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> CategoryOut:
    cat = await service.create_category(session, body)
    return CategoryOut.model_validate(cat)


@router.patch("/categories/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: UUID,
    body: CategoryUpdate,
    _staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> CategoryOut:
    cat = await service.update_category(session, category_id, body)
    return CategoryOut.model_validate(cat)


@router.get("/products", response_model=list[ProductOut])
async def list_products(
    category_id: UUID | None = None,
    category_slug: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    pet_type: str | None = Query(default=None, pattern="^(dog|cat|both)$"),
    brand: str | None = None,
    q: str | None = Query(default=None, max_length=100),
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    sort: str = Query(default="newest", pattern="^(newest|price_asc|price_desc|bestseller)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> list[ProductOut]:
    products = await service.list_products(
        session,
        category_id=category_id,
        category_slug=category_slug,
        status_filter=status_filter,
        pet_type=pet_type,
        brand=brand,
        q=q,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return [ProductOut.model_validate(p) for p in products]


@router.get("/products/by-slug/{slug}", response_model=ProductOut)
async def get_product_by_slug(
    slug: str,
    session: AsyncSession = Depends(get_db),
) -> ProductOut:
    product = await service.get_product_by_slug(session, slug)
    return ProductOut.model_validate(product)


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> ProductOut:
    product = await service.get_product(session, product_id)
    return ProductOut.model_validate(product)


@router.get("/products/{product_id}/stock")
async def get_product_stock(
    product_id: UUID,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Tồn kho / HSD gần nhất — cache ngắn ≤ 30s cho hộp biến thể trên storefront."""
    rows = await service.product_stock_snapshot(session, product_id)
    response.headers["Cache-Control"] = "public, max-age=30"
    return {"product_id": str(product_id), "variants": rows}


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductCreate,
    background: BackgroundTasks,
    _staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> ProductOut:
    product = await service.create_product(session, body)
    # Pattern 4.4: commit DB trước, rồi mới enqueue revalidate
    await session.commit()
    background.add_task(
        service.schedule_revalidate, product.slug, product.category_id
    )
    return ProductOut.model_validate(product)


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: UUID,
    body: ProductUpdate,
    background: BackgroundTasks,
    _staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> ProductOut:
    product = await service.update_product(session, product_id, body)
    await session.commit()
    background.add_task(
        service.schedule_revalidate, product.slug, product.category_id
    )
    return ProductOut.model_validate(product)


@router.get("/products/{product_id}/images", response_model=list[ProductImageOut])
async def list_product_images(
    product_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> list[ProductImageOut]:
    product = await service.get_product(session, product_id)
    return [ProductImageOut.model_validate(img) for img in product.images]


@router.put("/admin/products/{product_id}/images", response_model=list[ProductImageOut])
async def update_product_images(
    product_id: UUID,
    body: list[ProductImageUpdateIn],
    background: BackgroundTasks,
    _staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> list[ProductImageOut]:
    images = await service.replace_product_images(session, product_id, body)
    await session.commit()
    product = await service.get_product(session, product_id)
    background.add_task(
        service.schedule_revalidate, product.slug, product.category_id
    )
    return [ProductImageOut.model_validate(img) for img in images]


@router.post(
    "/products/{product_id}/variants",
    response_model=VariantOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_variant(
    product_id: UUID,
    body: VariantCreate,
    background: BackgroundTasks,
    _staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> VariantOut:
    product = await service.get_product(session, product_id)
    variant = await service.create_variant(session, product_id, body)
    await session.commit()
    background.add_task(
        service.schedule_revalidate, product.slug, product.category_id
    )
    return VariantOut.model_validate(variant)


@router.patch("/variants/{variant_id}", response_model=VariantOut)
async def update_variant(
    variant_id: UUID,
    body: VariantUpdate,
    background: BackgroundTasks,
    _staff: User = Depends(require_staff_user),
    session: AsyncSession = Depends(get_db),
) -> VariantOut:
    variant, product_slug = await service.update_variant(session, variant_id, body)
    product = await service.get_product(session, variant.product_id)
    await session.commit()
    background.add_task(
        service.schedule_revalidate, product_slug, product.category_id
    )
    return VariantOut.model_validate(variant)
