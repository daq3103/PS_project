import os
import uuid
import json
from unittest.mock import AsyncMock

import httpx
import pytest
import pyotp
from fastapi import HTTPException
from types import SimpleNamespace
from test_community import sessions
from app.core.database import get_db
from app.core.security import create_access_token, hash_token
from app.core.encryption import encrypt_secret
from app.models.user import User
from app.models.catalog import Category, Product
from app.modules.order.checkout import checkout
from app.modules.customer.auth_service import issue_session
from app.modules.order.schemas import CheckoutRequest

pytestmark = pytest.mark.skipif(not os.environ.get("COMMUNITY_TEST_DATABASE"), reason="isolated database required")

@pytest.mark.asyncio
async def test_public_catalog_and_totp():
    from app.main import app
    factory = sessions()
    secret = pyotp.random_base32()
    async with factory() as db:
        owner = User(full_name="Security QA", role="owner", is_active=True, totp_enabled=True, totp_secret_encrypted=encrypt_secret(secret))
        cat = Category(name="Security QA", slug=uuid.uuid4().hex, is_active=True)
        hidden = Category(name="Hidden", slug=uuid.uuid4().hex, is_active=False)
        db.add_all([owner, cat, hidden]); await db.flush()
        products = [Product(name="QA", slug=uuid.uuid4().hex, category_id=c.id, status=s, pet_type="both", has_expiry=False) for c, s in [(cat,"draft"),(cat,"active"),(hidden,"active")]]
        db.add_all(products)
        tokens = await issue_session(db, owner, mfa_verified=True)
        await db.commit()
    async def database():
        async with factory() as db:
            yield db
            await db.commit()
    app.dependency_overrides[get_db] = database
    token = tokens["access_token"]
    unverified = create_access_token(subject=str(owner.id), role="owner", extra={"auth_version":0})
    headers = {"Authorization":f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for query in ["", "?status=draft", "?status=archived"]:
                r = await client.get("/api/v1/products" + query)
                assert r.status_code == 200
                ids = {p["id"] for p in r.json()}
                assert str(products[0].id) not in ids and str(products[2].id) not in ids
            for product in [products[0], products[2]]:
                for suffix in [str(product.id), f"by-slug/{product.slug}", f"{product.id}/images", f"{product.id}/stock"]:
                    assert (await client.get("/api/v1/products/" + suffix)).status_code == 404
            assert (await client.get("/api/v1/admin/catalog/products")).status_code == 401
            r = await client.get("/api/v1/admin/catalog/products?status=draft", headers=headers)
            assert str(products[0].id) in {p["id"] for p in r.json()}
            for path in [f"categories/{cat.id}", f"products/{products[0].id}", f"variants/{uuid.uuid4()}"]:
                assert (await client.patch("/api/v1/" + path, headers={"Authorization":f"Bearer {unverified}"}, json={})).status_code == 403
            r = await client.patch(f"/api/v1/categories/{cat.id}", headers=headers, json={"name":"Updated QA"})
            assert r.status_code == 200, r.text
    finally:
        app.dependency_overrides.pop(get_db, None)

@pytest.mark.asyncio
async def test_checkout_retry_owner_and_payload():
    from app.modules.order.schemas import OrderOut
    from unittest.mock import patch
    body = CheckoutRequest(idempotency_key="qa-request-key", customer_name="QA", customer_phone="0900000000", shipping_address={}, payment_method="cod")
    digest = hash_token(json.dumps(body.model_dump(mode="json", exclude={"quote_id"}), sort_keys=True, separators=(",", ":")))
    owner = uuid.uuid4()
    existing = SimpleNamespace(id=uuid.uuid4(), user_id=owner, guest_token_hash=None, request_hash=digest)
    db = AsyncMock(); db.scalar.return_value = existing
    for user_id, guest in [(uuid.uuid4(),None),(None,"other-guest")]:
        with pytest.raises(HTTPException) as exc:
            await checkout(db, user_id=user_id, guest_token=guest, body=body)
        assert exc.value.status_code == 409
    existing.user_id=None; existing.guest_token_hash=hash_token("guest-one")
    with pytest.raises(HTTPException):
        await checkout(db, user_id=None, guest_token="guest-two", body=body)
    existing.user_id=owner
    changed=body.model_copy(update={"customer_phone":"0999999999"})
    with pytest.raises(HTTPException):
        await checkout(db, user_id=owner, guest_token=None, body=changed)
    db.scalars.return_value=SimpleNamespace(all=lambda:[])
    with patch.object(OrderOut, "from_order", return_value="same-order"):
        assert await checkout(db, user_id=owner, guest_token=None, body=body) == ("same-order", [])
        existing.user_id=None
        assert await checkout(db, user_id=None, guest_token="guest-one", body=body) == ("same-order", [])
