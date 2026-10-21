from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import (
    clear_auth_cookies,
    clear_guest_cookie,
    set_auth_cookies,
    set_csrf_cookie,
    set_guest_cookie,
)
from app.core.database import get_db
from app.core.deps import get_current_user_optional
from app.core.rate_limit import client_ip, enforce_rate_limit
from app.core.security import new_csrf_token, new_guest_token
from app.models.user import User
from app.modules.cart import service as cart_service
from app.modules.customer import auth_service
from app.modules.customer.schemas import (
    AuthMeOut,
    LoginRequest,
    ProfileUpdateIn,
    RegisterRequest,
    UserOut,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_db),
    guest_token: str | None = Cookie(default=None, alias="guest_token"),
) -> UserOut:
    user = await auth_service.register_user(
        session,
        full_name=body.full_name,
        password=body.password,
        email=str(body.email) if body.email else None,
        phone=body.phone,
    )
    tokens = await auth_service.issue_session(session, user)
    header_guest = request.headers.get("X-Guest-Token")
    gtoken = header_guest or guest_token
    if gtoken:
        await cart_service.merge_guest_cart_into_user(session, guest_token=gtoken, user_id=user.id)
        clear_guest_cookie(response)
    await session.commit()
    set_auth_cookies(response, **tokens)
    return UserOut.model_validate(user)


@router.post("/login", response_model=UserOut)
async def login(
    body: LoginRequest,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_db),
    guest_token: str | None = Cookie(default=None, alias="guest_token"),
) -> UserOut:
    account_key = str(body.email or body.phone or "")
    ip = client_ip(request)
    await enforce_rate_limit(
        key=f"rl:login:{ip}:{account_key}",
        limit=5,
        window_seconds=60,
    )
    user = await auth_service.authenticate_user(
        session,
        password=body.password,
        email=str(body.email) if body.email else None,
        phone=body.phone,
    )
    tokens = await auth_service.issue_session(session, user)
    header_guest = request.headers.get("X-Guest-Token")
    gtoken = header_guest or guest_token
    if gtoken:
        await cart_service.merge_guest_cart_into_user(session, guest_token=gtoken, user_id=user.id)
        clear_guest_cookie(response)
    await session.commit()
    set_auth_cookies(response, **tokens)
    return UserOut.model_validate(user)


@router.post("/refresh", response_model=UserOut)
async def refresh(
    response: Response,
    session: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias="refresh_token"),
) -> UserOut:
    if not refresh_token:
        from fastapi import HTTPException

        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")
    user, tokens = await auth_service.rotate_refresh(session, raw_refresh=refresh_token)
    await session.commit()
    set_auth_cookies(response, **tokens)
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias="refresh_token"),
) -> None:
    await auth_service.revoke_refresh(session, raw_refresh=refresh_token)
    await session.commit()
    clear_auth_cookies(response)


@router.get("/me", response_model=AuthMeOut)
async def me(
    response: Response,
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    guest_token: str | None = Cookie(default=None, alias="guest_token"),
    csrf_token: str | None = Cookie(default=None, alias="csrf_token"),
) -> AuthMeOut:
    header_guest = request.headers.get("X-Guest-Token")
    gtoken = header_guest or guest_token
    if not user and not gtoken:
        gtoken = new_guest_token()
        set_guest_cookie(response, gtoken)
    if not csrf_token:
        csrf_token = new_csrf_token()
        set_csrf_cookie(response, csrf_token)
    return AuthMeOut(
        user=UserOut.model_validate(user) if user else None,
        csrf_token=csrf_token,
        guest_token=gtoken,
    )


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: ProfileUpdateIn,
    user: User = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_db),
) -> UserOut:
    if not user:
        from fastapi import HTTPException

        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    updated = await auth_service.update_profile(
        session,
        user,
        full_name=body.full_name,
        phone=body.phone,
    )
    await session.commit()
    return UserOut.model_validate(updated)
