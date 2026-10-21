from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_csrf_token,
    new_refresh_token,
    verify_password,
)
from app.models.user import RefreshToken, User

settings = get_settings()

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _sanitize_full_name(value: str) -> str:
    """Strip HTML tags and collapse whitespace to mitigate stored XSS."""
    cleaned = _HTML_TAG_RE.sub("", value)
    return " ".join(cleaned.split())[:150]


async def register_user(
    session: AsyncSession,
    *,
    full_name: str,
    password: str,
    email: str | None,
    phone: str | None,
) -> User:
    if email:
        exists = await session.scalar(select(User.id).where(User.email == email))
        if exists:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Email đã được sử dụng")
    if phone:
        exists = await session.scalar(select(User.id).where(User.phone == phone))
        if exists:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="SĐT đã được sử dụng")

    user = User(
        full_name=_sanitize_full_name(full_name),
        email=email,
        phone=phone,
        password_hash=hash_password(password),
        role="customer",
    )
    session.add(user)
    await session.flush()
    return user


async def authenticate_user(
    session: AsyncSession,
    *,
    password: str,
    email: str | None,
    phone: str | None,
) -> User:
    stmt = select(User)
    if email:
        stmt = stmt.where(User.email == email)
    else:
        stmt = stmt.where(User.phone == phone)
    user = await session.scalar(stmt)
    if not user or not user.password_hash or not verify_password(user.password_hash, password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Sai thông tin đăng nhập")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Tài khoản đã bị khóa")
    return user


async def issue_session(session: AsyncSession, user: User) -> dict[str, str]:
    access = create_access_token(subject=str(user.id), role=user.role)
    refresh = new_refresh_token()
    csrf = new_csrf_token()
    row = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh),
        expires_at=datetime.now(UTC) + timedelta(days=settings.jwt_refresh_ttl_days),
    )
    session.add(row)
    await session.flush()
    return {"access_token": access, "refresh_token": refresh, "csrf_token": csrf}


async def rotate_refresh(
    session: AsyncSession, *, raw_refresh: str
) -> tuple[User, dict[str, str]]:
    th = hash_token(raw_refresh)
    token = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == th))
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Refresh token không hợp lệ")

    # Reuse of revoked token → revoke entire chain for user
    if token.revoked_at is not None:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == token.user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Phát hiện reuse refresh token — toàn bộ phiên đã bị thu hồi",
        )

    if token.expires_at < datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Refresh token hết hạn")

    user = await session.get(User, token.user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User không hợp lệ")

    token.revoked_at = datetime.now(UTC)
    new_raw = new_refresh_token()
    new_row = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_raw),
        parent_token_id=token.id,
        expires_at=datetime.now(UTC) + timedelta(days=settings.jwt_refresh_ttl_days),
    )
    session.add(new_row)
    await session.flush()

    access = create_access_token(subject=str(user.id), role=user.role)
    csrf = new_csrf_token()
    return user, {"access_token": access, "refresh_token": new_raw, "csrf_token": csrf}


async def revoke_refresh(session: AsyncSession, *, raw_refresh: str | None) -> None:
    if not raw_refresh:
        return
    th = hash_token(raw_refresh)
    token = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == th))
    if token and token.revoked_at is None:
        token.revoked_at = datetime.now(UTC)
        await session.flush()


async def revoke_all_user_tokens(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def update_profile(
    session: AsyncSession,
    user: User,
    full_name: str | None = None,
    phone: str | None = None,
) -> User:
    if phone is not None and phone != user.phone:
        exists = await session.scalar(select(User.id).where(User.phone == phone))
        if exists:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="SĐT đã được sử dụng")
    if full_name is not None:
        user.full_name = _sanitize_full_name(full_name)
    if phone is not None:
        user.phone = phone
    await session.flush()
    return user
