"""An owner can combine staff permissions; API guards enforce each assignment."""

import os
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pyotp
import pytest
from sqlalchemy import select
from test_community import sessions

from app.core.database import get_db
from app.core.encryption import encrypt_secret
from app.core.security import create_access_token, hash_token
from app.models.user import RefreshToken, StaffRoleChange, User
from app.modules.customer.auth_service import issue_session

pytestmark = pytest.mark.skipif(
    not os.environ.get("COMMUNITY_TEST_DATABASE"),
    reason="Use scripts/test_community.py for isolated PostgreSQL",
)


@pytest.mark.asyncio
async def test_owner_assigns_combined_permissions_and_revokes_old_session():
    from app.main import app

    factory = sessions()
    secret = pyotp.random_base32()
    async with factory() as session:
        owner = User(
            id=uuid.uuid4(), full_name="Owner QA", role="owner", is_active=True,
            totp_enabled=True, totp_secret_encrypted=encrypt_secret(secret),
        )
        customer = User(
            id=uuid.uuid4(), full_name="Staff Candidate", role="customer", is_active=True,
            email=f"staff-{uuid.uuid4().hex[:8]}@example.com",
            username="qa_tester_pethome",
        )
        another_owner = User(
            id=uuid.uuid4(), full_name="Second Owner", role="owner", is_active=True,
        )
        session.add_all([owner, customer, another_owner])
        await session.flush()
        refresh = RefreshToken(
            user_id=customer.id, token_hash=hash_token("old-staff-refresh"),
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        session.add(refresh)
        tokens = await issue_session(session, owner, mfa_verified=True)
        await session.commit()
        owner_id, customer_id, another_owner_id = owner.id, customer.id, another_owner.id

    async def database():
        async with factory() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = database
    owner_token = tokens["access_token"]
    old_token = create_access_token(subject=str(customer_id), role="customer", extra={"auth_version": 0})
    headers = {"Authorization": f"Bearer {owner_token}"}
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            listed = await client.get("/api/v1/admin/staff/users", headers=headers)
            assert listed.status_code == 200
            assert str(customer_id) not in {row["id"] for row in listed.json()}
            searched = await client.get("/api/v1/admin/staff/users", params={"q": "Staff Candidate"}, headers=headers)
            assert searched.status_code == 200 and searched.json()[0]["id"] == str(customer_id)
            by_username = await client.get("/api/v1/admin/staff/users", params={"q": "QA_TESTER_PETHOME"}, headers=headers)
            assert by_username.status_code == 200
            assert [row["id"] for row in by_username.json()] == [str(customer_id)]
            assert by_username.json()[0]["username"] == "qa_tester_pethome"

            endpoint = f"/api/v1/admin/staff/users/{customer_id}/permissions"
            assert (await client.patch(endpoint, json={"permissions": ["warehouse"]})).status_code == 401
            combined = await client.patch(
                endpoint,
                headers=headers,
                json={"permissions": ["customer_support", "warehouse"]},
            )
            assert combined.status_code == 200, combined.text
            assert combined.json()["staff_permissions"] == ["customer_support", "warehouse"]
            assert combined.json()["role"] == "warehouse_staff"
            assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"})).status_code == 401
            async with factory() as session:
                row = await session.scalar(select(RefreshToken).where(RefreshToken.user_id == customer_id))
                assert row and row.revoked_at is not None
                changes = (await session.scalars(select(StaffRoleChange))).all()
                assert len(changes) == 1 and changes[0].actor_user_id == owner_id

            combined_token = create_access_token(subject=str(customer_id), role="warehouse_staff", extra={"auth_version": 1})
            staff_headers = {"Authorization": f"Bearer {combined_token}"}
            assert (await client.get("/api/v1/admin/lots", headers=staff_headers)).status_code == 200
            assert (await client.get("/api/v1/admin/reviews", headers=staff_headers)).status_code == 200
            assert (await client.get("/api/v1/admin/community/posts", headers=staff_headers)).status_code == 403
            assert (await client.get("/api/v1/admin/staff/users", headers=staff_headers)).status_code == 403
            assert (await client.get("/api/v1/admin/promotions", headers=staff_headers)).status_code == 403

            reduced = await client.patch(
                endpoint,
                headers=headers,
                json={"permissions": ["customer_support"]},
            )
            assert reduced.status_code == 200 and reduced.json()["role"] == "cskh_staff"
            support_token = create_access_token(subject=str(customer_id), role="cskh_staff", extra={"auth_version": 2})
            support_headers = {"Authorization": f"Bearer {support_token}"}
            assert (await client.get("/api/v1/admin/lots", headers=support_headers)).status_code == 403
            assert (await client.get("/api/v1/admin/reviews", headers=support_headers)).status_code == 200
            assert (await client.patch(
                f"/api/v1/categories/{uuid.uuid4()}", headers=support_headers, json={},
            )).status_code == 403
            assert (await client.patch(
                f"/api/v1/admin/staff/users/{another_owner_id}/permissions",
                headers=headers,
                json={"permissions": []},
            )).status_code == 403
            history = await client.get("/api/v1/admin/staff/changes", headers=headers)
            assert history.status_code == 200 and len(history.json()) == 2
            demoted = await client.patch(
                endpoint,
                headers=headers,
                json={"permissions": []},
            )
            assert demoted.status_code == 200 and demoted.json()["role"] == "customer"
            customer_token = create_access_token(subject=str(customer_id), role="customer", extra={"auth_version": 3})
            assert (await client.get(
                "/api/v1/admin/reviews", headers={"Authorization": f"Bearer {customer_token}"}
            )).status_code == 403
    finally:
        app.dependency_overrides.clear()
