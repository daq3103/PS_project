"""Middleware: staff with totp_enabled must send X-TOTP-Code on admin mutations."""

from __future__ import annotations

from uuid import UUID

import pyotp
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.encryption import decrypt_secret_str
from app.core.security import decode_token
from app.models.user import User

ADMIN_PREFIX = "/api/v1/admin"
ENROLL_PATHS = (
    "/api/v1/admin/totp/enroll",
    "/api/v1/admin/totp/verify",
)


class StaffTotpMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if not path.startswith(ADMIN_PREFIX):
            return await call_next(request)
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)
        if any(path.startswith(p) for p in ENROLL_PATHS):
            return await call_next(request)

        token = request.cookies.get("access_token")
        if not token:
            auth = request.headers.get("Authorization", "")
            if auth.lower().startswith("bearer "):
                token = auth[7:].strip()
        if not token:
            return await call_next(request)

        try:
            payload = decode_token(token)
        except Exception:
            return await call_next(request)

        from app.core.database import AsyncSessionLocal

        user_id = payload.get("sub")
        if not user_id:
            return JSONResponse({"detail": "Invalid token"}, status_code=401)

        async with AsyncSessionLocal() as session:
            user = await session.get(User, UUID(str(user_id)))
            # The database role is authoritative: an older JWT may predate a role change.
            if user and user.role not in ("owner", "warehouse_staff", "cskh_staff"):
                return await call_next(request)
            if not user or not user.totp_enabled:
                return JSONResponse(
                    {"detail": "TOTP enrollment required for staff"},
                    status_code=403,
                )
            if not user.totp_secret_encrypted:
                return JSONResponse({"detail": "TOTP secret missing"}, status_code=403)

            code = request.headers.get("X-TOTP-Code", "").strip()
            if not code:
                return JSONResponse({"detail": "X-TOTP-Code header required"}, status_code=403)

            secret = decrypt_secret_str(user.totp_secret_encrypted)
            totp = pyotp.TOTP(secret)
            if not totp.verify(code, valid_window=1):
                return JSONResponse({"detail": "Invalid TOTP code"}, status_code=403)

        return await call_next(request)
