from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import set_csrf_cookie, set_guest_cookie
from app.core.database import get_db
from app.core.deps import AuthContext, get_auth_context
from app.core.security import new_csrf_token
from app.modules.cart import service
from app.modules.cart.schemas import CartItemAdd, CartItemUpdate, CartOut

router = APIRouter(prefix="/api/v1/cart", tags=["cart"])


def _ids(ctx: AuthContext) -> tuple[UUID | None, str | None]:
    return (ctx.user.id if ctx.user else None, ctx.guest_token)


@router.get("", response_model=CartOut)
async def get_cart(
    response: Response,
    session: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> CartOut:
    user_id, guest = _ids(ctx)
    cart, minted = await service.get_cart_out(session, user_id=user_id, guest_token=guest)
    if minted:
        set_guest_cookie(response, minted)
        set_csrf_cookie(response, new_csrf_token())
    return cart


@router.post("/items", response_model=CartOut)
async def add_cart_item(
    body: CartItemAdd,
    response: Response,
    session: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> CartOut:
    user_id, guest = _ids(ctx)
    if not user_id:
        raise HTTPException(401, "Vui lòng đăng nhập để thêm sản phẩm vào giỏ hàng.")
    cart, minted = await service.add_item(
        session,
        user_id=user_id,
        guest_token=guest,
        variant_id=body.variant_id,
        qty=body.qty,
    )
    if minted:
        set_guest_cookie(response, minted)
        set_csrf_cookie(response, new_csrf_token())
    return cart


@router.patch("/items/{item_id}", response_model=CartOut)
async def update_cart_item(
    item_id: UUID,
    body: CartItemUpdate,
    session: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> CartOut:
    user_id, guest = _ids(ctx)
    return await service.update_item(
        session, user_id=user_id, guest_token=guest, item_id=item_id, qty=body.qty
    )


@router.delete("/items/{item_id}", response_model=CartOut)
async def delete_cart_item(
    item_id: UUID,
    session: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> CartOut:
    user_id, guest = _ids(ctx)
    return await service.remove_item(
        session, user_id=user_id, guest_token=guest, item_id=item_id
    )
