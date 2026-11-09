"""Owner verifies at sign-in; staff permissions remain independent of MFA."""
import os
import uuid
from contextlib import asynccontextmanager

import httpx
import pyotp
import pytest
from sqlalchemy import select
from test_community import sessions

from app.core.database import get_db
from app.core.encryption import encrypt_secret
from app.core.security import create_access_token, hash_password
from app.models.user import RefreshToken, User

pytestmark = pytest.mark.skipif(not os.environ.get("COMMUNITY_TEST_DATABASE"), reason="isolated database required")
PASSWORD = "qa-password-only-123"


@asynccontextmanager
async def environment(monkeypatch, *, enabled=True):
    from app.main import app
    from app.modules.customer import router as auth_router
    from app.modules.admin import router as admin_router
    async def no_limit(**kwargs):
        pass
    monkeypatch.setattr(auth_router, "enforce_rate_limit", no_limit)
    monkeypatch.setattr(admin_router, "enforce_rate_limit", no_limit)
    factory = sessions()
    secret = pyotp.random_base32()
    async with factory() as db:
        owner = User(full_name="Session QA", email=f"session-{uuid.uuid4().hex}@example.com", role="owner", is_active=True,
                     password_hash=hash_password(PASSWORD), totp_enabled=enabled,
                     totp_secret_encrypted=encrypt_secret(secret) if enabled else None)
        db.add(owner); await db.commit()
    async def database():
        async with factory() as db:
            yield db
            await db.commit()
    app.dependency_overrides[get_db] = database
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            yield client, owner, secret, factory
    finally:
        app.dependency_overrides.pop(get_db, None)


def csrf(client):
    return {"X-CSRF-Token": client.cookies.get("csrf_token", "")}


@pytest.mark.asyncio
async def test_owner_login_verify_once_refresh_logout_and_old_session(monkeypatch):
    from app.main import app
    async with environment(monkeypatch) as (client, owner, secret, factory):
        credentials = {"email": owner.email, "password": PASSWORD}
        challenge = await client.post("/api/v1/auth/login", json=credentials)
        assert challenge.status_code == 200 and challenge.json() == {"requires_totp": True}
        assert not client.cookies.get("access_token") and not client.cookies.get("refresh_token")
        assert (await client.get("/api/v1/admin/categories")).status_code in (401,404)
        wrong = "000000" if pyotp.TOTP(secret).now() != "000000" else "111111"
        assert (await client.post("/api/v1/auth/login", json={**credentials,"totp_code":wrong})).status_code == 401
        signed = await client.post("/api/v1/auth/login", json={**credentials,"totp_code":pyotp.TOTP(secret).now()})
        assert signed.status_code == 200 and signed.json()["role"] == "owner"
        assert (await client.get("/api/v1/auth/me")).json()["admin_verified"] is True
        # Repeated writes use the verified session; there is no per-operation OTP.
        for index in range(2):
            result = await client.post("/api/v1/categories", json={"name":"QA","slug":uuid.uuid4().hex}, headers=csrf(client))
            assert result.status_code == 201, result.text
        old_access = client.cookies.get("access_token")
        assert (await client.post("/api/v1/auth/refresh", headers=csrf(client))).status_code == 200
        assert (await client.get("/api/v1/auth/me")).json()["admin_verified"] is True
        assert (await client.get("/api/v1/admin/catalog/products")).status_code == 200
        signed_access = client.cookies.get("access_token")
        assert (await client.post("/api/v1/auth/logout", headers=csrf(client))).status_code == 204
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as attacker:
            for access in (old_access, signed_access):
                assert (await attacker.get("/api/v1/admin/catalog/products", headers={"Authorization":f"Bearer {access}"})).status_code == 401
            legacy = create_access_token(subject=str(owner.id), role="owner", extra={"auth_version":owner.auth_version})
            assert (await attacker.get("/api/v1/admin/catalog/products", headers={"Authorization":f"Bearer {legacy}"})).status_code == 403
        assert (await client.post("/api/v1/auth/login", json=credentials)).json()["requires_totp"] is True


@pytest.mark.asyncio
async def test_first_setup_is_restricted_then_unlocks_session(monkeypatch):
    async with environment(monkeypatch, enabled=False) as (client, owner, secret, factory):
        signed = await client.post("/api/v1/auth/login", json={"email":owner.email,"password":PASSWORD})
        assert signed.status_code == 200 and signed.json()["totp_enabled"] is False
        assert (await client.get("/api/v1/admin/catalog/products")).status_code == 403
        assert (await client.post("/api/v1/categories", json={"name":"Blocked","slug":"blocked"}, headers=csrf(client))).status_code == 403
        enrollment = await client.post("/api/v1/admin/totp/enroll", headers=csrf(client))
        assert enrollment.status_code == 200
        key = enrollment.json()["secret"]  # Ephemeral test-account key, never production.
        code = pyotp.TOTP(key).now()
        result = await client.post("/api/v1/admin/totp/verify", json={"code":code}, headers=csrf(client))
        assert result.status_code == 200, result.text
        assert (await client.get("/api/v1/auth/me")).json()["admin_verified"] is True
        assert (await client.get("/api/v1/admin/catalog/products")).status_code == 200


@pytest.mark.asyncio
async def test_staff_without_mfa_can_moderate_but_not_assign_permissions(monkeypatch):
    async with environment(monkeypatch) as (client, owner, secret, factory):
        async with factory() as db:
            support = User(full_name="Support QA", email=f"staff-{uuid.uuid4().hex}@example.com", password_hash=hash_password(PASSWORD), role="cskh_staff", staff_permissions=["customer_support", "rescue_manage"], is_active=True, totp_enabled=False)
            warehouse = User(full_name="Warehouse QA", email=f"warehouse-{uuid.uuid4().hex}@example.com", password_hash=hash_password(PASSWORD), role="warehouse_staff", staff_permissions=["warehouse"], is_active=True, totp_enabled=False)
            db.add_all([support,warehouse]); await db.commit()
        for staff, expected in [(support,404),(warehouse,403)]:
            client.cookies.clear()
            result = await client.post("/api/v1/auth/login", json={"email":staff.email,"password":PASSWORD})
            assert result.status_code == 200 and "requires_totp" not in result.json()
            # Support reaches moderation's record lookup, warehouse is denied by permission.
            result = await client.post(f"/api/v1/admin/reviews/{uuid.uuid4()}/approve", json={"approve":True}, headers=csrf(client))
            assert result.status_code == expected, result.text
            assert (await client.patch(f"/api/v1/admin/staff/users/{owner.id}/permissions", json={"permissions":[]}, headers=csrf(client))).status_code == 403
            assert (await client.post("/api/v1/admin/totp/enroll", headers=csrf(client))).status_code == 403
