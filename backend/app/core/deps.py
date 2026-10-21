"""Shared FastAPI dependencies: current user, guest token, optional auth."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User


@dataclass
class AuthContext:
    user: User | None
    guest_token: str | None


async def get_current_user_optional(
    request: Request,
    session: AsyncSession = Depends(get_db),
    access_token: str | None = Cookie(default=None, alias="access_token"),
) -> User | None:
    token = access_token
    if not token:
        auth = request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        return None
    try:
        payload = decode_token(token)
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user_id = payload.get("sub")
    if not user_id:
        return None
    user = await session.get(User, UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User inactive or missing")
    return user


async def get_current_user(
    user: User | None = Depends(get_current_user_optional),
) -> User:
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


async def get_auth_context(
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
    guest_token: str | None = Cookie(default=None, alias="guest_token"),
) -> AuthContext:
    # Allow X-Guest-Token header for API clients / Next.js BFF
    header_guest = request.headers.get("X-Guest-Token")
    return AuthContext(user=user, guest_token=header_guest or guest_token)


async def require_customer(user: User = Depends(get_current_user)) -> User:
    return user


STAFF_ROLES = frozenset({"owner", "warehouse_staff", "cskh_staff"})


async def require_staff_user(
    user: User = Depends(get_current_user),
) -> User:
    if user.role not in STAFF_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Staff access required")
    return user


async def require_owner(
    user: User = Depends(require_staff_user),
) -> User:
    if user.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Owner access required")
    return user
