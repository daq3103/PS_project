"""Envelope encryption AES-256-GCM for secrets at rest (api tokens, TOTP, etc.)."""

from __future__ import annotations

import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

_NONCE_LEN = 12  # AES-GCM standard nonce


def _key_bytes() -> bytes:
    raw = get_settings().secret_encryption_key.strip()
    if not raw:
        raise RuntimeError("SECRET_ENCRYPTION_KEY is not set")
    try:
        key = bytes.fromhex(raw)
    except ValueError as exc:
        raise RuntimeError("SECRET_ENCRYPTION_KEY must be 64 hex characters (32 bytes)") from exc
    if len(key) != 32:
        raise RuntimeError("SECRET_ENCRYPTION_KEY must be exactly 32 bytes (64 hex chars)")
    return key


def encrypt_secret(plaintext: str | bytes) -> bytes:
    """Return nonce || ciphertext||tag (BYTEA-safe)."""
    data = plaintext.encode("utf-8") if isinstance(plaintext, str) else plaintext
    nonce = secrets.token_bytes(_NONCE_LEN)
    ct = AESGCM(_key_bytes()).encrypt(nonce, data, None)
    return nonce + ct


def decrypt_secret(blob: bytes) -> bytes:
    if len(blob) <= _NONCE_LEN:
        raise ValueError("ciphertext too short")
    nonce, ct = blob[:_NONCE_LEN], blob[_NONCE_LEN:]
    return AESGCM(_key_bytes()).decrypt(nonce, ct, None)


def decrypt_secret_str(blob: bytes) -> str:
    return decrypt_secret(blob).decode("utf-8")


def generate_encryption_key_hex() -> str:
    """Helper for ops: print a new master key (do not log in prod)."""
    return os.urandom(32).hex()
