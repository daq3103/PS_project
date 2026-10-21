"""Feature switch, abuse limits and server-side Turnstile verification."""

import httpx
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.rate_limit import client_ip, enforce_rate_limit


class CommunityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if path.startswith(("/api/v1/community", "/api/v1/admin/community")):
            if not get_settings().community_enabled and path != "/api/v1/community/config":
                return JSONResponse(
                    {"detail": "Trạm cứu hộ đang tạm ngưng"},
                    status_code=503,
                    headers={"Cache-Control": "no-store"},
                )
            response = await call_next(request)
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
        return await call_next(request)


async def limit(request: Request, user_id, action, count, seconds=3600):
    await enforce_rate_limit(
        key=f"community:{action}:user:{user_id}", limit=count, window_seconds=seconds
    )
    await enforce_rate_limit(
        key=f"community:{action}:ip:{client_ip(request)}",
        limit=max(count * 3, 10),
        window_seconds=seconds,
    )


async def verify_turnstile(request: Request):
    """Declared before DB-backed auth dependencies: external HTTP precedes autobegin."""
    settings = get_settings()
    if not settings.community_turnstile_secret:
        if settings.app_env != "development":
            raise HTTPException(503, "Chưa cấu hình xác minh chống spam")
        return
    body = await request.json()
    token = body.get("turnstile_token")
    if not isinstance(token, str) or not token or len(token) > 2048:
        raise HTTPException(422, "Vui lòng xác minh chống spam")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": settings.community_turnstile_secret,
                    "response": token,
                    "remoteip": client_ip(request),
                },
            )
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Dịch vụ xác minh tạm gián đoạn, vui lòng thử lại") from exc
    if not result.get("success") or (
        settings.community_turnstile_hostname
        and result.get("hostname") != settings.community_turnstile_hostname
    ):
        raise HTTPException(422, "Xác minh không hợp lệ hoặc đã hết hạn")
