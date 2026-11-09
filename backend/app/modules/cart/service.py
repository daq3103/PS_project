from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import new_guest_token
from app.models.catalog import Product, ProductImage, ProductVariant
from app.models.commerce import Cart, CartItem
from app.modules.cart.schemas import CartItemOut, CartOut


async def _get_or_create_cart(
    session: AsyncSession,
    *,
    user_id: UUID | None,
    guest_token: str | None,
) -> tuple[Cart, str | None]:
    """Return cart and possibly newly minted guest_token."""
    minted: str | None = None
    if user_id or guest_token:
        await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                              {"key": f"cart:{user_id or guest_token}"})
    if user_id:
        cart = await session.scalar(select(Cart).where(Cart.user_id == user_id))
        if cart:
            return cart, None
        cart = Cart(user_id=user_id)
        session.add(cart)
        await session.flush()
        return cart, None

    token = guest_token or new_guest_token()
    if not guest_token:
        minted = token
    cart = await session.scalar(select(Cart).where(Cart.guest_token == token))
    if cart:
        return cart, minted
    cart = Cart(guest_token=token)
    session.add(cart)
    await session.flush()
    return cart, minted


async def get_cart_out(
    session: AsyncSession,
    *,
    user_id: UUID | None,
    guest_token: str | None,
) -> tuple[CartOut, str | None]:
    cart, minted = await _get_or_create_cart(
        session, user_id=user_id, guest_token=guest_token
    )
    items = await _load_items(session, cart.id)
    return _to_cart_out(cart.id, items), minted


async def add_item(
    session: AsyncSession,
    *,
    user_id: UUID | None,
    guest_token: str | None,
    variant_id: UUID,
    qty: int,
) -> tuple[CartOut, str | None]:
    variant = await session.get(ProductVariant, variant_id)
    if not variant or not variant.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Biến thể không tồn tại")

    cart, minted = await _get_or_create_cart(
        session, user_id=user_id, guest_token=guest_token
    )
    existing = await session.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id, CartItem.variant_id == variant_id
        )
    )
    existing_qty = existing.qty if existing else 0
    new_total = existing_qty + qty
    if new_total > variant.cached_available_qty:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Chỉ còn {variant.cached_available_qty} sản phẩm trong kho",
        )

    await session.execute(
        text("""
            INSERT INTO cart_items (cart_id, variant_id, qty)
            VALUES (:cart_id, :variant_id, :qty)
            ON CONFLICT (cart_id, variant_id)
            DO UPDATE SET qty = EXCLUDED.qty, updated_at = NOW()
        """),
        {"cart_id": cart.id, "variant_id": variant_id, "qty": new_total},
    )
    await session.flush()
    items = await _load_items(session, cart.id)
    return _to_cart_out(cart.id, items), minted


async def update_item(
    session: AsyncSession,
    *,
    user_id: UUID | None,
    guest_token: str | None,
    item_id: UUID,
    qty: int,
) -> CartOut:
    cart, _ = await _get_or_create_cart(session, user_id=user_id, guest_token=guest_token)
    item = await session.get(CartItem, item_id)
    if not item or item.cart_id != cart.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mục giỏ không tồn tại")

    variant = await session.get(ProductVariant, item.variant_id)
    if variant and qty > variant.cached_available_qty:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Chỉ còn {variant.cached_available_qty} sản phẩm trong kho",
        )

    item.qty = qty
    await session.flush()
    items = await _load_items(session, cart.id)
    return _to_cart_out(cart.id, items)


async def remove_item(
    session: AsyncSession,
    *,
    user_id: UUID | None,
    guest_token: str | None,
    item_id: UUID,
) -> CartOut:
    cart, _ = await _get_or_create_cart(session, user_id=user_id, guest_token=guest_token)
    item = await session.get(CartItem, item_id)
    if not item or item.cart_id != cart.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mục giỏ không tồn tại")
    await session.delete(item)
    await session.flush()
    items = await _load_items(session, cart.id)
    return _to_cart_out(cart.id, items)


async def merge_guest_cart_into_user(
    session: AsyncSession, *, guest_token: str, user_id: UUID
) -> None:
    """Gộp giỏ guest → user: cùng variant cộng dồn qty (ON CONFLICT DO UPDATE)."""
    for key in sorted((f"cart:{user_id}", f"cart:{guest_token}")):
        await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key})
    guest_cart = await session.scalar(select(Cart).where(Cart.guest_token == guest_token))
    if not guest_cart:
        return

    user_cart = await session.scalar(select(Cart).where(Cart.user_id == user_id))
    if not user_cart:
        guest_cart.user_id = user_id
        guest_cart.guest_token = None
        await session.flush()
        await _clamp_merged_cart(session, guest_cart.id)
        return

    await session.execute(
        text("""
            INSERT INTO cart_items (cart_id, variant_id, qty)
            SELECT :user_cart_id, variant_id, qty
            FROM cart_items
            WHERE cart_id = :guest_cart_id
            ON CONFLICT (cart_id, variant_id)
            DO UPDATE SET qty = cart_items.qty + EXCLUDED.qty, updated_at = NOW()
        """),
        {"user_cart_id": user_cart.id, "guest_cart_id": guest_cart.id},
    )
    await session.execute(
        text("DELETE FROM cart_items WHERE cart_id = :gid"),
        {"gid": guest_cart.id},
    )
    await session.delete(guest_cart)
    await session.flush()
    await _clamp_merged_cart(session, user_cart.id)


async def _clamp_merged_cart(session: AsyncSession, cart_id: UUID) -> None:
    await session.execute(text("""
        UPDATE cart_items ci SET qty = LEAST(ci.qty, 99, GREATEST(1, pv.cached_available_qty))
        FROM product_variants pv WHERE ci.variant_id = pv.id AND ci.cart_id = :cid
    """), {"cid": cart_id})


async def _load_items(session: AsyncSession, cart_id: UUID) -> list[CartItemOut]:
    stmt = (
        select(CartItem, ProductVariant, Product)
        .join(ProductVariant, ProductVariant.id == CartItem.variant_id)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(CartItem.cart_id == cart_id)
        .order_by(CartItem.created_at)
    )
    rows = (await session.execute(stmt)).all()
    image_rows = (await session.scalars(select(ProductImage)
        .where(ProductImage.product_id.in_({product.id for _item, _variant, product in rows}))
        .order_by(ProductImage.sort_order, ProductImage.created_at))).all() if rows else []
    out: list[CartItemOut] = []
    for item, variant, product in rows:
        image = next((i for i in image_rows if i.product_id == product.id and i.variant_id == variant.id), None)
        if image is None:
            image = next((i for i in image_rows if i.product_id == product.id and i.variant_id is None), None)
        available = (
            variant.is_active
            and product.status == "active"
            and variant.cached_available_qty > 0
        )
        label = None
        if not variant.is_active or product.status != "active":
            label = "Không còn bán"
        elif variant.cached_available_qty <= 0:
            label = "Hết hàng"
        out.append(
            CartItemOut(
                id=item.id,
                variant_id=item.variant_id,
                qty=item.qty,
                sku=variant.sku,
                title=variant.title,
                product_name=product.name,
                product_slug=product.slug,
                image_url=image.r2_url if image else None,
                unit_price=variant.price,
                cached_available_qty=variant.cached_available_qty,
                is_available=available,
                unavailable_label=label,
                updated_at=item.updated_at,
            )
        )
    return out


def _to_cart_out(cart_id: UUID, items: list[CartItemOut]) -> CartOut:
    subtotal = sum(
        (i.unit_price or 0) * i.qty for i in items if i.is_available and i.unit_price is not None
    )
    return CartOut(
        id=cart_id,
        items=items,
        item_count=sum(i.qty for i in items),
        subtotal=subtotal,
    )
