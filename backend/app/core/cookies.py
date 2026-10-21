"""Cookie helpers for auth + guest + CSRF."""

from __future__ import annotations

from typing import Any

from fastapi import Response

from app.core.config import get_settings

settings = get_settings()


def _secure() -> bool:
    return settings.app_env != "development"


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
) -> None:
    common: dict[str, Any] = {
        "httponly": True,
        "secure": _secure(),
        "samesite": "lax",
        "path": "/",
    }
    response.set_cookie(
        "access_token",
        access_token,
        max_age=settings.jwt_access_ttl_minutes * 60,
        **common,
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        max_age=settings.jwt_refresh_ttl_days * 24 * 3600,
        **common,
    )
    # CSRF must be readable by JS (double-submit)
    response.set_cookie(
        "csrf_token",
        csrf_token,
        max_age=settings.jwt_refresh_ttl_days * 24 * 3600,
        httponly=False,
        secure=_secure(),
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    for name in ("access_token", "refresh_token", "csrf_token"):
        response.delete_cookie(name, path="/")


def set_guest_cookie(response: Response, guest_token: str) -> None:
    response.set_cookie(
        "guest_token",
        guest_token,
        max_age=30 * 24 * 3600,
        httponly=True,
        secure=_secure(),
        samesite="lax",
        path="/",
    )


def set_csrf_cookie(response: Response, csrf_token: str) -> None:
    response.set_cookie(
        "csrf_token",
        csrf_token,
        max_age=30 * 24 * 3600,
        httponly=False,
        secure=_secure(),
        samesite="lax",
        path="/",
    )


def clear_guest_cookie(response: Response) -> None:
    response.delete_cookie("guest_token", path="/")
