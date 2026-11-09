"""One-use email recovery links. Raw tokens never enter the database or logs."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import smtplib
import ssl
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.security import hash_password, hash_token
from app.models.user import PasswordResetToken, RefreshToken, User

RESET_TTL = timedelta(minutes=30)
CODE_TTL = timedelta(minutes=10)
MAX_CODE_ATTEMPTS = 5


def delivery_available() -> bool:
    settings = get_settings()
    base = settings.app_public_url.strip()
    parsed = urlsplit(base)
    local = parsed.hostname in {"localhost", "127.0.0.1"}
    valid_url = (
        (parsed.scheme == "https" or (parsed.scheme == "http" and local))
        and bool(parsed.netloc)
        and not parsed.username
        and not parsed.password
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    )
    if settings.password_reset_email_provider == "gmail":
        sender = settings.gmail_user.strip()
        configured = (
            sender.endswith("@gmail.com")
            and sender.count("@") == 1
            and bool(sender.removesuffix("@gmail.com"))
            and not any(c.isspace() for c in sender)
            and bool(settings.gmail_app_password.get_secret_value().strip())
        )
    else:
        configured = bool(settings.resend_api_key and settings.resend_from)
    return bool(configured and valid_url)


def account_rate_key(email: str) -> str:
    return hashlib.sha256(email.strip().casefold().encode()).hexdigest()


async def create_reset_token(session: AsyncSession, email: str) -> str | None:
    user = await session.scalar(
        select(User).where(func.lower(User.email) == email.strip().lower()).with_for_update()
    )
    if not user or not user.is_active or not user.password_hash or (user.username and not user.email_verified):
        return None
    now = datetime.now(UTC)
    await session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    raw = secrets.token_urlsafe(48)
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=now + RESET_TTL,
        )
    )
    await session.flush()
    return raw


def _code_hash(token_hash: str, code: str) -> str:
    # A keyed hash prevents brute-forcing a six-digit code from a database-only leak.
    return hmac.new(
        get_settings().jwt_secret.encode(), f"{token_hash}:{code}".encode(), hashlib.sha256
    ).hexdigest()


async def create_reset_code(session: AsyncSession, email: str) -> str | None:
    raw = await create_reset_token(session, email)
    if raw is None:
        return None
    record = await session.scalar(select(PasswordResetToken).where(
        PasswordResetToken.token_hash == hash_token(raw)
    ))
    code = f"{secrets.randbelow(1_000_000):06d}"
    record.code_hash = _code_hash(record.token_hash, code)
    record.expires_at = datetime.now(UTC) + CODE_TTL
    await session.flush()
    return code


async def verify_reset_code(session: AsyncSession, email: str, code: str) -> str | None:
    user = await session.scalar(select(User).where(
        func.lower(User.email) == email.strip().lower()
    ).with_for_update())
    if not user or not user.is_active or not user.password_hash:
        return None
    record = await session.scalar(select(PasswordResetToken).where(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.code_hash.is_not(None),
        PasswordResetToken.target_email.is_(None),
    ).order_by(PasswordResetToken.created_at.desc()).limit(1).with_for_update())
    now = datetime.now(UTC)
    if not record or record.expires_at <= now or record.attempts >= MAX_CODE_ATTEMPTS:
        return None
    record.attempts += 1
    if not hmac.compare_digest(record.code_hash, _code_hash(record.token_hash, code)):
        await session.flush()
        return None
    record.used_at = now
    # Only a successful code exchange grants a high-entropy, single-use reset token.
    raw = await create_reset_token(session, email)
    token = await session.scalar(select(PasswordResetToken).where(
        PasswordResetToken.token_hash == hash_token(raw)
    ))
    token.expires_at = now + CODE_TTL
    await session.flush()
    return raw


async def send_reset_code_email(email: str, code: str) -> None:
    await _deliver_email(email, {
        "subject": "Mã đặt lại mật khẩu PetHome",
        "html": (
            "<p>Mã đặt lại mật khẩu PetHome của bạn:</p>"
            f'<p style="font-size:32px;letter-spacing:6px"><strong>{code}</strong></p>'
            "<p>Mã có hiệu lực 10 phút và chỉ dùng một lần. Không chia sẻ mã này.</p>"
            "<p>Nếu bạn không yêu cầu, hãy bỏ qua email này.</p>"
        ),
        "text": f"Mã đặt lại mật khẩu PetHome: {code}\n"
                "Mã có hiệu lực 10 phút và chỉ dùng một lần. Không chia sẻ mã này.\n"
                "Nếu bạn không yêu cầu, hãy bỏ qua email này.",
    })


async def _deliver_email(email: str, payload: dict) -> None:
    settings = get_settings()
    payload = {**payload, "from": settings.resend_from, "to": [email]}
    try:
        if settings.password_reset_email_provider == "gmail":
            # smtplib is blocking: keep the API event loop free during TLS/login/delivery.
            await run_in_threadpool(_send_gmail, email, payload)
            return
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json=payload,
            )
            response.raise_for_status()
    except (httpx.HTTPError, smtplib.SMTPException, OSError) as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chưa gửi được email. Vui lòng thử lại sau.",
        ) from exc


def _send_gmail(email: str, payload: dict) -> None:
    settings = get_settings()
    sender = settings.gmail_user.strip()
    message = EmailMessage()
    message["From"] = formataddr(("PetHome", sender))
    message["To"] = email
    message["Subject"] = payload["subject"]
    message.set_content(payload["text"])
    message.add_alternative(payload["html"], subtype="html")
    # Gmail app passwords may be copied as four groups separated by spaces.
    password = "".join(settings.gmail_app_password.get_secret_value().split())
    with smtplib.SMTP_SSL(
        "smtp.gmail.com", 465, timeout=15, context=ssl.create_default_context()
    ) as client:
        client.login(sender, password)
        refused = client.send_message(message, from_addr=sender, to_addrs=[email])
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)


async def consume_reset_token(
    session: AsyncSession, raw_token: str, new_password: str
) -> None:
    now = datetime.now(UTC)
    candidate = await session.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == hash_token(raw_token))
    )
    if not candidate:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Liên kết không hợp lệ hoặc đã hết hạn.")
    # All recovery operations lock the user first to serialize resends and consumption.
    user = await session.get(User, candidate.user_id, with_for_update=True)
    record = await session.scalar(select(PasswordResetToken).where(
        PasswordResetToken.id == candidate.id
    ).with_for_update().execution_options(populate_existing=True))
    if record.used_at or record.expires_at <= now or record.code_hash is not None or record.target_email is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Liên kết không hợp lệ hoặc đã hết hạn.")
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Liên kết không hợp lệ hoặc đã hết hạn.")
    user.password_hash = hash_password(new_password)
    user.auth_version += 1
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    await session.flush()
