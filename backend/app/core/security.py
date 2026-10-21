"""Auth & crypto helpers (JWT/CSRF/Argon2 stubs for Week 1; full auth in Week 2/5)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

_ph = PasswordHasher()
_settings = get_settings()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def hash_token(token: str) -> str:
    """SHA-256 hex digest — store refresh token hashes only."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(*, subject: str, role: str, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=_settings.jwt_access_ttl_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _settings.jwt_secret, algorithms=["HS256"], leeway=_settings.jwt_clock_skew_seconds)


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def new_guest_token() -> str:
    """≥256-bit entropy guest cart token (Week 2)."""
    return secrets.token_urlsafe(32)


def verify_hmac_sha256(*, secret: bytes | str, body: bytes, signature_hex: str) -> bool:
    key = secret.encode("utf-8") if isinstance(secret, str) else secret
    expected = hmac.new(key, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_hex)
