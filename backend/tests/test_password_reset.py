"""Recovery links cannot be reused and changing credentials invalidates prior sessions."""

import os
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from test_community import sessions

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import hash_token
from app.models.user import PasswordResetToken, RefreshToken
from app.modules.customer import auth_service, password_reset

pytestmark = pytest.mark.skipif(
    not os.environ.get("COMMUNITY_TEST_DATABASE"),
    reason="Use scripts/test_community.py for isolated PostgreSQL",
)


@pytest.fixture(autouse=True)
def use_test_email_provider(monkeypatch):
    monkeypatch.setattr(get_settings(), "password_reset_email_provider", "resend")


@pytest.mark.asyncio
async def test_password_reset_is_generic_one_use_and_revokes_sessions(monkeypatch):
    from app.main import app

    factory = sessions()
    email = f"recovery-{uuid.uuid4().hex[:8]}@example.com"
    async with factory() as session:
        user = await auth_service.register_user(
            session, full_name="Recovery QA", password="old-password-123", email=email, phone=None
        )
        old_tokens = await auth_service.issue_session(session, user)
        await session.commit()
        user_id = user.id

    settings = get_settings()
    old_config = (settings.app_public_url, settings.resend_api_key, settings.resend_from)
    settings.app_public_url = "http://localhost"
    settings.resend_api_key = "test-key"
    settings.resend_from = "PetHome <hello@example.com>"
    delivered = []

    async def fake_email(address, token):
        delivered.append((address, token))

    async def allow_test_requests(**_kwargs):
        return None

    async def database():
        async with factory() as session:
            yield session
            await session.commit()

    monkeypatch.setattr(password_reset, "send_reset_code_email", fake_email)
    monkeypatch.setattr("app.modules.customer.router.enforce_rate_limit", allow_test_requests)
    app.dependency_overrides[get_db] = database
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            config = await client.get("/api/v1/auth/password-reset/config")
            assert config.json() == {"available": True}
            missing = await client.post(
                "/api/v1/auth/password-reset/request",
                json={"email": "nobody@example.com"},
            )
            requested = await client.post(
                "/api/v1/auth/password-reset/request", json={"email": email}
            )
            assert missing.status_code == requested.status_code == 202
            assert missing.json() == requested.json()
            assert len(delivered) == 1 and delivered[0][0] == email
            code = delivered[0][1]
            assert len(code) == 6 and code.isascii() and code.isdigit()
            async with factory() as session:
                stored = await session.scalar(
                    select(PasswordResetToken).where(PasswordResetToken.user_id == user_id)
                )
                assert stored and stored.code_hash != code

            verified = await client.post("/api/v1/auth/password-reset/verify-code", json={
                "email": email, "code": code,
            })
            assert verified.status_code == 200
            raw = verified.json()["token"]
            assert (await client.post("/api/v1/auth/password-reset/verify-code", json={
                "email": email, "code": code,
            })).status_code == 400

            bad = await client.post(
                "/api/v1/auth/password-reset/confirm",
                json={"token": "invalid-token-long-enough", "password": "new-password-123"},
            )
            assert bad.status_code == 400
            changed = await client.post(
                "/api/v1/auth/password-reset/confirm",
                json={"token": raw, "password": "new-password-123"},
            )
            assert changed.status_code == 204
            assert (await client.post(
                "/api/v1/auth/password-reset/confirm",
                json={"token": raw, "password": "another-password"},
            )).status_code == 400
            old_access = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {old_tokens['access_token']}"},
            )
            assert old_access.status_code == 401
            async with factory() as session:
                refresh_record = await session.scalar(select(RefreshToken).where(
                    RefreshToken.token_hash == hash_token(old_tokens["refresh_token"])
                ))
                assert refresh_record and refresh_record.revoked_at is not None
            client.cookies.set("refresh_token", old_tokens["refresh_token"])
            client.cookies.set("csrf_token", old_tokens["csrf_token"])
            assert (await client.post("/api/v1/auth/refresh", headers={
                "X-CSRF-Token": old_tokens["csrf_token"]
            })).status_code == 401
            client.cookies.clear()
            assert (await client.post("/api/v1/auth/login", json={
                "email": email, "password": "old-password-123"
            })).status_code == 401
            assert (await client.post("/api/v1/auth/login", json={
                "email": email, "password": "new-password-123"
            })).status_code == 200
    finally:
        app.dependency_overrides.clear()
        settings.app_public_url, settings.resend_api_key, settings.resend_from = old_config


@pytest.mark.asyncio
async def test_code_attempts_persist_and_resend_invalidates_old_code(monkeypatch):
    from app.main import app

    factory = sessions()
    email = f"otp-{uuid.uuid4().hex[:8]}@example.com"
    async with factory() as session:
        await auth_service.register_user(
            session, full_name="Code QA", password="old-password-123", email=email, phone=None
        )
        code = await password_reset.create_reset_code(session, email)
        await session.commit()

    async def database():
        async with factory() as session:
            yield session
            await session.commit()

    async def allow_test_requests(**_kwargs):
        pass

    monkeypatch.setattr("app.modules.customer.router.enforce_rate_limit", allow_test_requests)
    app.dependency_overrides[get_db] = database
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            wrong = "000000" if code != "000000" else "111111"
            for _ in range(5):
                assert (await client.post("/api/v1/auth/password-reset/verify-code", json={
                    "email": email, "code": wrong,
                })).status_code == 400
            assert (await client.post("/api/v1/auth/password-reset/verify-code", json={
                "email": email, "code": code,
            })).status_code == 400
            async with factory() as session:
                record = await session.scalar(select(PasswordResetToken).where(
                    PasswordResetToken.code_hash.is_not(None),
                    PasswordResetToken.used_at.is_(None),
                ).order_by(PasswordResetToken.created_at.desc()))
                assert record.attempts == 5
                first = await password_reset.create_reset_code(session, email)
                # Deterministic different code makes invalidation check non-flaky.
                monkeypatch.setattr(password_reset.secrets, "randbelow", lambda _: (int(first) + 1) % 1_000_000)
                second = await password_reset.create_reset_code(session, email)
                await session.commit()
            assert (await client.post("/api/v1/auth/password-reset/verify-code", json={
                "email": email, "code": first,
            })).status_code == 400
            async with factory() as session:
                record = await session.scalar(select(PasswordResetToken).where(
                    PasswordResetToken.used_at.is_(None),
                    PasswordResetToken.code_hash.is_not(None),
                ).order_by(PasswordResetToken.created_at.desc()))
                record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
                await session.commit()
            assert (await client.post("/api/v1/auth/password-reset/verify-code", json={
                "email": email, "code": second,
            })).status_code == 400
            assert (await client.post("/api/v1/auth/password-reset/verify-code", json={
                "email": "no-such-user@example.com", "code": "123456",
            })).status_code == 400
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_expired_link_and_disabled_delivery(monkeypatch):
    from app.main import app

    factory = sessions()
    email = f"expired-{uuid.uuid4().hex[:8]}@example.com"
    async with factory() as session:
        user = await auth_service.register_user(
            session, full_name="Expired QA", password="old-password-123", email=email, phone=None
        )
        await session.commit()

    settings = get_settings()
    old_config = (settings.app_public_url, settings.resend_api_key, settings.resend_from)
    settings.app_public_url = "http://localhost"
    settings.resend_api_key = ""
    settings.resend_from = "hello@example.com"
    assert not password_reset.delivery_available()

    async def database():
        async with factory() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = database
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            assert (await client.get("/api/v1/auth/password-reset/config")).json() == {"available": False}
            assert (await client.post("/api/v1/auth/password-reset/request", json={
                "email": email
            })).status_code == 503
            async with factory() as session:
                raw = await password_reset.create_reset_token(session, email)
                assert raw
                record = await session.scalar(
                    select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
                )
                assert record
                record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
                await session.commit()
            assert (await client.post("/api/v1/auth/password-reset/confirm", json={
                "token": raw, "password": "new-password-123"
            })).status_code == 400
    finally:
        app.dependency_overrides.clear()
        settings.app_public_url, settings.resend_api_key, settings.resend_from = old_config
