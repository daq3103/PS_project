import os
import uuid
import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from test_community import sessions
from app.core.database import get_db
from app.models.user import User
from app.modules.customer import google_auth, email_verification

pytestmark = pytest.mark.skipif(not os.environ.get("COMMUNITY_TEST_DATABASE"), reason="Isolated database required")

@pytest.mark.asyncio
async def test_username_google_link_and_verified_recovery_email(monkeypatch):
    from app.main import app
    factory = sessions()
    async def database():
        async with factory() as session:
            yield session
            await session.commit()
    async def allow(**kwargs):
        pass
    app.dependency_overrides[get_db] = database
    monkeypatch.setattr("app.modules.customer.router.enforce_rate_limit", allow)
    monkeypatch.setattr(google_auth, "enforce_rate_limit", allow)
    monkeypatch.setattr(email_verification, "enforce_rate_limit", allow)
    suffix = uuid.uuid4().hex[:10]
    username = "qa_" + suffix
    email = suffix + "@example.com"
    claims = {"sub": suffix, "email": email, "email_verified": True, "name": "Google QA"}
    monkeypatch.setattr(google_auth, "verify_credential", lambda *_: claims)
    delivered = []
    async def delivery(address, payload):
        delivered.append(payload["text"])
    monkeypatch.setattr(email_verification.recovery, "delivery_available", lambda: True)
    monkeypatch.setattr(email_verification.recovery, "_deliver_email", delivery)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            registered = await client.post("/api/v1/auth/register", json={"username": username.upper(), "password": "Password123", "full_name": "QA"})
            assert registered.status_code == 201, registered.text
            assert registered.json()["username"] == username
            user_id = registered.json()["id"]
            csrf = client.cookies.get("csrf_token")
            headers = {"X-CSRF-Token": csrf}
            assert (await client.post("/api/v1/auth/me/email/request", json={"email": email}, headers=headers)).status_code == 202
            import re
            code = re.search(r"\b[0-9]{6}\b", delivered[0]).group()
            assert (await client.post("/api/v1/auth/me/email/verify", json={"email": email, "code": code}, headers=headers)).status_code == 204
            assert (await client.get("/api/v1/auth/me")).json()["user"]["email_verified"]
            client.cookies.clear()
            collision = await client.post("/api/v1/auth/google", json={"id_token": "x" * 30})
            assert collision.status_code == 409
            login = await client.post("/api/v1/auth/login", json={"username": username.upper(), "password": "Password123"})
            assert login.status_code == 200
            linked = await client.post("/api/v1/auth/google", json={"id_token": "x" * 30, "link": True}, headers={"X-CSRF-Token": client.cookies.get("csrf_token")})
            assert linked.status_code == 200, linked.text
            assert linked.json()["google_linked"]
            client.cookies.clear()
            login = await client.post("/api/v1/auth/google", json={"id_token": "x" * 30})
            assert login.status_code == 200 and login.json()["id"] == user_id
            client.cookies.clear()
            claims["sub"] = "other-" + suffix
            claims["email"] = "other-" + email
            created = await client.post("/api/v1/auth/google", json={"id_token": "x" * 30})
            assert created.status_code == 200 and created.json()["username"] is None
            client.cookies.clear()
            assert (await client.post("/api/v1/auth/register", json={"username": username, "password": "Password123", "full_name": "QA"})).status_code == 409
            assert (await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123", "full_name": "QA"})).status_code == 422
    finally:
        app.dependency_overrides.clear()

def test_google_rejects_wrong_nonce_and_unverified_email(monkeypatch):
    from app.core.config import Settings
    monkeypatch.setattr(google_auth, "get_settings", lambda: Settings(_env_file=None, google_client_id="client"))
    claims = {"sub": "abc", "email": "a@gmail.com", "email_verified": True, "nonce": "correct"}
    monkeypatch.setattr(google_auth, "verify_oauth2_token", lambda *args: claims)
    with pytest.raises(HTTPException):
        google_auth.verify_credential("token", "wrong")
    claims["email_verified"] = False
    with pytest.raises(HTTPException):
        google_auth.verify_credential("token", "correct")


@pytest.mark.asyncio
async def test_explicit_gmail_approval_preserves_owner_and_is_consumed(monkeypatch):
    from app.main import app
    from app.modules.customer.auth_service import register_user
    factory = sessions()
    email = f"approved-{uuid.uuid4().hex[:10]}@gmail.com"
    async with factory() as session:
        user = await register_user(session, full_name="Owner QA", password="Password123", email=email, phone=None)
        user.role = "owner"
        user.google_email_link_allowed = True
        await session.commit()
        user_id = user.id
    async def database():
        async with factory() as session:
            yield session
            await session.commit()
    async def allow(**kwargs):
        pass
    claims = {"sub": str(user_id), "email": email, "email_verified": True}
    monkeypatch.setattr(google_auth, "verify_credential", lambda *_: claims)
    monkeypatch.setattr(google_auth, "enforce_rate_limit", allow)
    app.dependency_overrides[get_db] = database
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/google", json={"id_token": "x" * 30})
            assert response.status_code == 200, response.text
            assert response.json()["id"] == str(user_id)
            assert response.json()["role"] == "owner"
        async with factory() as session:
            user = await session.get(User, user_id)
            assert user.google_id == str(user_id)
            assert not user.google_email_link_allowed
    finally:
        app.dependency_overrides.clear()
