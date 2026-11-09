"""Shared FastAPI dependencies: current user, guest token, optional auth."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import RefreshToken, User

OWNER_SETUP_PATHS = frozenset({
    "/api/v1/auth/me", "/api/v1/auth/logout", "/api/v1/auth/refresh",
    "/api/v1/admin/totp/enroll", "/api/v1/admin/totp/verify", "/api/v1/admin/totp/status",
})


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
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.") from exc
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.")
    user_id = payload.get("sub")
    if not user_id:
        return None
    user = await session.get(User, UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không còn hoạt động.")
    if payload.get("auth_version", 0) != user.auth_version:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.")
    request.state.admin_verified = False
    if payload.get("sid"):
        try:
            session_id = UUID(payload["sid"])
        except (ValueError, TypeError) as exc:
            raise HTTPException(401, "Phiên đăng nhập không hợp lệ.") from exc
        login_session = await session.get(RefreshToken, session_id)
        if (not login_session or login_session.user_id != user.id
                or login_session.revoked_at is not None
                or login_session.expires_at <= datetime.now(UTC)):
            raise HTTPException(401, "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.")
        request.state.admin_verified = bool(user.totp_enabled and login_session.mfa_verified)
    if user.role == "owner" and not request.state.admin_verified and request.url.path not in OWNER_SETUP_PATHS:
        raise HTTPException(403, "Vui lòng xác minh hai bước khi đăng nhập quản trị viên.")
    return user


async def get_current_user(
    user: User | None = Depends(get_current_user_optional),
) -> User:
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Vui lòng đăng nhập để tiếp tục.")
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
STAFF_PERMISSIONS = frozenset({"warehouse", "customer_support", "rescue_manage", "rescue_care", "rescue_finance", "platform_manage"})


def has_staff_permission(user: User, permission: str) -> bool:
    if user.role == "owner":
        return True
    if user.role not in STAFF_ROLES:
        return False
    permissions = user.staff_permissions or []
    return permission in permissions or (permission in STAFF_PERMISSIONS and "platform_manage" in permissions)


async def require_staff_user(
    user: User = Depends(get_current_user),
) -> User:
    if user.role not in STAFF_ROLES or (
        user.role != "owner"
        and not any(has_staff_permission(user, permission) for permission in STAFF_PERMISSIONS)
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Bạn cần quyền nhân viên để thực hiện thao tác này.")
    return user


async def require_warehouse_or_owner(user: User = Depends(require_staff_user)) -> User:
    if not has_staff_permission(user, "warehouse"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Bạn cần quyền quản lý kho để thực hiện thao tác này.")
    return user


async def require_shop_staff(user: User = Depends(require_staff_user)) -> User:
    if not (has_staff_permission(user, "warehouse") or has_staff_permission(user, "customer_support")):
        raise HTTPException(403, "Bạn cần quyền nhân viên Shop để xem phần này.")
    return user


async def require_cskh_or_owner(user: User = Depends(require_staff_user)) -> User:
    if not has_staff_permission(user, "customer_support"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Bạn cần quyền chăm sóc khách hàng để thực hiện thao tác này.")
    return user


async def require_owner(
    user: User = Depends(require_staff_user),
) -> User:
    if user.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Chỉ quản trị viên mới được thực hiện thao tác này.")
    return user


async def require_platform_manager(user: User = Depends(require_staff_user)) -> User:
    """Full application operations, without authority to assign staff permissions."""
    if not has_staff_permission(user, "platform_manage"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Bạn cần quyền quản lý nền tảng để thực hiện thao tác này.")
    return user
