"""CSRF double-submit middleware for browser mutations."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
SKIP_PREFIXES = (
    "/docs",
    "/openapi.json",
    "/healthz",
    "/readyz",
    "/api/v1/webhooks",
    # Login/register establish session; CSRF áp dụng sau khi đã có cookie auth
    "/api/v1/auth/login",
    "/api/v1/auth/register",
)


class CsrfMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if request.method in SAFE_METHODS or any(path.startswith(p) for p in SKIP_PREFIXES):
            return await call_next(request)

        # Server-to-server / OpenAPI testing: skip if no cookies at all
        # but browser requests with cookies must send CSRF.
        has_auth_cookie = bool(
            request.cookies.get("access_token")
            or request.cookies.get("refresh_token")
            or request.cookies.get("csrf_token")
            or request.cookies.get("guest_token")
            or request.cookies.get("rescue_session")
        )
        if not has_auth_cookie:
            return await call_next(request)

        cookie_csrf = request.cookies.get("csrf_token")
        header_csrf = request.headers.get("X-CSRF-Token")
        if not cookie_csrf or not header_csrf or cookie_csrf != header_csrf:
            return JSONResponse({"detail": "Phiên đăng nhập không hợp lệ. Vui lòng tải lại trang rồi thử lại."}, status_code=403)

        return await call_next(request)
