from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog import Category, Product, ProductImage, ProductVariant
from app.modules.catalog.schemas import (
    CategoryCreate,
    CategoryUpdate,
    ProductCreate,
    ProductImageUpdateIn,
    ProductUpdate,
    VariantCreate,
    VariantUpdate,
)
from app.worker.enqueue import enqueue_revalidate_product


async def list_categories(session: AsyncSession, *, active_only: bool = False) -> list[Category]:
    stmt = select(Category).order_by(Category.sort_order, Category.name)
    if active_only:
        stmt = stmt.where(Category.is_active.is_(True))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_category(session: AsyncSession, data: CategoryCreate) -> Category:
    existing = await session.scalar(select(Category).where(Category.slug == data.slug))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Category slug already exists")
    cat = Category(**data.model_dump())
    session.add(cat)
    await session.flush()
    return cat


async def update_category(
    session: AsyncSession, category_id: UUID, data: CategoryUpdate
) -> Category:
    cat = await session.get(Category, category_id)
    if not cat:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Category not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    await session.flush()
    return cat


async def get_product_by_slug(session: AsyncSession, slug: str) -> Product:
    stmt = (
        select(Product)
        .where(Product.slug == slug)
        .options(selectinload(Product.variants), selectinload(Product.images))
    )
    product = await session.scalar(stmt)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


async def get_product(session: AsyncSession, product_id: UUID) -> Product:
    stmt = (
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.variants), selectinload(Product.images))
    )
    product = await session.scalar(stmt)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


async def get_category_by_slug(session: AsyncSession, slug: str) -> Category:
    cat = await session.scalar(select(Category).where(Category.slug == slug))
    if not cat:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Category not found")
    return cat


async def list_products(
    session: AsyncSession,
    *,
    category_id: UUID | None = None,
    category_slug: str | None = None,
    status_filter: str | None = None,
    pet_type: str | None = None,
    brand: str | None = None,
    q: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    sort: str = "newest",
    limit: int = 50,
    offset: int = 0,
) -> list[Product]:
    stmt = select(Product).options(selectinload(Product.variants), selectinload(Product.images))

    if category_slug and not category_id:
        cat = await get_category_by_slug(session, category_slug)
        category_id = cat.id
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if status_filter:
        stmt = stmt.where(Product.status == status_filter)
    if pet_type:
        stmt = stmt.where(Product.pet_type.in_([pet_type, "both"]))
    if brand:
        stmt = stmt.where(Product.brand.ilike(brand))
    if q:
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(term),
                Product.brand.ilike(term),
                Product.short_description.ilike(term),
                Product.slug.ilike(term),
            )
        )

    if min_price is not None or max_price is not None:
        stmt = stmt.join(ProductVariant).where(ProductVariant.is_active.is_(True))
        if min_price is not None:
            stmt = stmt.where(ProductVariant.price >= min_price)
        if max_price is not None:
            stmt = stmt.where(ProductVariant.price <= max_price)

    if sort == "price_asc":
        stmt = stmt.order_by(Product.created_at.desc())  # refined after load
    elif sort == "bestseller":
        stmt = stmt.order_by(Product.total_sold.desc(), Product.created_at.desc())
    else:
        stmt = stmt.order_by(Product.created_at.desc())

    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    products = list(result.scalars().unique().all())

    if sort == "price_asc":
        products.sort(
            key=lambda p: min((v.price for v in p.variants if v.is_active), default=10**18)
        )
    elif sort == "price_desc":
        products.sort(
            key=lambda p: max((v.price for v in p.variants if v.is_active), default=-1),
            reverse=True,
        )
    return products


async def product_stock_snapshot(session: AsyncSession, product_id: UUID) -> list[dict]:
    product = await get_product(session, product_id)
    return [
        {
            "variant_id": str(v.id),
            "title": v.title,
            "sku": v.sku,
            "cached_available_qty": v.cached_available_qty,
            "nearest_expiry_date": v.nearest_expiry_date.isoformat()
            if v.nearest_expiry_date
            else None,
            "price": v.price,
            "is_active": v.is_active,
        }
        for v in product.variants
    ]


async def create_product(session: AsyncSession, data: ProductCreate) -> Product:
    existing = await session.scalar(select(Product).where(Product.slug == data.slug))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Product slug already exists")
    cat = await session.get(Category, data.category_id)
    if not cat:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid category_id")

    payload = data.model_dump(exclude={"variants"})
    product = Product(**payload)
    session.add(product)
    await session.flush()

    for v in data.variants:
        session.add(ProductVariant(product_id=product.id, **v.model_dump()))
    await session.flush()
    return await get_product(session, product.id)


async def update_product(
    session: AsyncSession, product_id: UUID, data: ProductUpdate
) -> Product:
    product = await get_product(session, product_id)
    old_slug = product.slug
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(product, k, v)
    await session.flush()

    # After commit, ARQ will revalidate — enqueue registered via session events in router
    product._revalidate_slug = product.slug  # type: ignore[attr-defined]
    product._revalidate_old_slug = old_slug  # type: ignore[attr-defined]
    return product


async def create_variant(
    session: AsyncSession, product_id: UUID, data: VariantCreate
) -> ProductVariant:
    product = await get_product(session, product_id)
    existing = await session.scalar(
        select(ProductVariant).where(ProductVariant.sku == data.sku)
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="SKU already exists")
    variant = ProductVariant(product_id=product.id, **data.model_dump())
    session.add(variant)
    await session.flush()
    return variant


async def update_variant(
    session: AsyncSession, variant_id: UUID, data: VariantUpdate
) -> tuple[ProductVariant, str]:
    """Returns (variant, product_slug) — price/stock changes trigger ISR revalidate."""
    variant = await session.get(ProductVariant, variant_id)
    if not variant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Variant not found")
    product = await session.get(Product, variant.product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(variant, k, v)
    await session.flush()
    return variant, product.slug


async def replace_product_images(
    session: AsyncSession, product_id: UUID, images: list[ProductImageUpdateIn]
) -> list[ProductImage]:
    await get_product(session, product_id)
    await session.execute(
        text("""
            DELETE FROM product_images WHERE product_id = :pid
        """),
        {"pid": product_id},
    )
    out: list[ProductImage] = []
    for idx, img in enumerate(images):
        pi = ProductImage(
            product_id=product_id,
            variant_id=img.variant_id,
            r2_url=img.r2_url,
            alt_text=img.alt_text,
            sort_order=img.sort_order if img.sort_order != 0 else idx,
        )
        session.add(pi)
        out.append(pi)
    await session.flush()
    return out


async def schedule_revalidate(product_slug: str, category_id: UUID | None = None) -> None:
    await enqueue_revalidate_product(product_slug, str(category_id) if category_id else None)
