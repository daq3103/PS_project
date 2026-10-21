"""PostgreSQL workflow, privacy, proxy, upload and durable job regression tests."""

import asyncio
import io
import os
import uuid
from datetime import timedelta

import httpx
import pytest
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.requests import Request

from app.core.config import get_settings
from app.core.rate_limit import client_ip
from app.core.security import create_access_token, decode_token
from app.models.community import (
    AdoptionRequest,
    CommunityAuditLog,
    CommunityNotification,
)
from app.models.user import User
from app.modules.community import schemas, service, upload_service

pytestmark = pytest.mark.skipif(
    not os.environ.get("COMMUNITY_TEST_DATABASE"),
    reason="Use scripts/test_community.py for isolated PostgreSQL",
)


def sessions():
    assert get_settings().database_url.endswith(os.environ["COMMUNITY_TEST_DATABASE"])
    return async_sessionmaker(
        create_async_engine(get_settings().database_url, poolclass=NullPool),
        expire_on_commit=False,
        autoflush=False,
    )


async def user(factory, role="customer"):
    async with factory() as session:
        row = User(id=uuid.uuid4(), full_name="Rescue test", role=role, is_active=True)
        session.add(row)
        await session.commit()
        return row


def post_input(kind="lost_pet"):
    return schemas.CommunityPostCreateIn(
        post_type=kind,
        title="Tìm bé thử nghiệm",
        pet_type="cat",
        province_id=1,
        province_name="Client must not control name",
        contact_phone="0901234567",
    )


async def published(factory, staff, kind="adoption"):
    async with factory() as session:
        post = await service.create_post(
            session, staff.id, post_input(kind), str(uuid.uuid4()), adoption=kind == "adoption"
        )
        if kind != "adoption":
            await service.admin_moderate(session, post, "approve", staff.id, None)
        await session.commit()
        return post


@pytest.mark.asyncio
async def test_post_idempotency_moderation_and_conflicting_edits():
    factory = sessions()
    owner = await user(factory)
    key = str(uuid.uuid4())
    async with factory() as session:
        post = await service.create_post(session, owner.id, post_input(), key)
        await session.commit()
        ident, slug = post.id, post.slug
    async with factory() as session:
        retry = await service.create_post(session, owner.id, post_input(), key)
        assert retry.id == ident
        assert retry.province_name == "Hà Nội"
        assert await service.get_public_post_by_slug(session, slug) is None
        await session.commit()
    async with factory() as session:
        altered = post_input().model_copy(update={"title": "Nội dung khác"})
        with pytest.raises(HTTPException) as error:
            await service.create_post(session, owner.id, altered, key)
        assert error.value.status_code == 409
    async with factory() as session:
        post = await service.get_post(session, ident, lock=True)
        await service.admin_moderate(session, post, "approve", owner.id, None)
        version = post.version
        await session.commit()

    async def edit(title):
        async with factory() as session:
            try:
                post = await service.owner_post(session, ident, owner.id, lock=True)
                await service.update_post(
                    session,
                    post,
                    owner.id,
                    schemas.CommunityPostUpdateIn(title=title, version=version),
                )
                await session.commit()
                return 200
            except HTTPException as exc:
                await session.rollback()
                return exc.status_code

    assert sorted(await asyncio.gather(edit("Tên sửa lần một"), edit("Tên sửa lần hai"))) == [
        200,
        409,
    ]
    async with factory() as session:
        post = await service.get_post(session, ident)
        assert post.moderation_status == "pending"
        assert post.version == version + 1
        assert await service.get_public_post_by_slug(session, slug) is None


@pytest.mark.asyncio
async def test_concurrent_adoption_selection_completion_and_withdrawal():
    factory = sessions()
    staff, first, second = [await user(factory, role) for role in ["owner", "customer", "customer"]]
    post = await published(factory, staff)
    data = schemas.AdoptionCreateIn(
        applicant_name="Người nhận",
        applicant_phone="0901234567",
        applicant_address="Địa chỉ thử nghiệm",
        living_condition="Có chỗ ở và kinh nghiệm nuôi mèo",
    )
    ids = []
    for applicant in (first, second):
        async with factory() as session:
            row = await service.create_adoption_request(
                session, post.id, applicant.id, data, str(uuid.uuid4())
            )
            await service.adoption_action(
                session,
                row.id,
                staff.id,
                schemas.AdoptionActionIn(action="contact", admin_note="SECRET STAFF NOTE"),
            )
            ids.append(row.id)
            await session.commit()

    async def approve(ident):
        async with factory() as session:
            try:
                await service.adoption_action(
                    session, ident, staff.id, schemas.AdoptionActionIn(action="approve")
                )
                await session.commit()
                return ident
            except HTTPException:
                await session.rollback()
                return None

    winners = [i for i in await asyncio.gather(*(approve(i) for i in ids)) if i]
    assert len(winners) == 1
    async with factory() as session:
        winner = await session.get(AdoptionRequest, winners[0])
        public = schemas.AdoptionOut.model_validate(service.adoption_out(winner)).model_dump()
        assert "admin_note" not in public
        await service.adoption_action(
            session, winner.id, staff.id, schemas.AdoptionActionIn(action="complete")
        )
        await session.commit()
    async with factory() as session:
        await service.adoption_action(
            session, winners[0], staff.id, schemas.AdoptionActionIn(action="complete")
        )
        await session.commit()
        assert (await service.get_post(session, post.id)).lifecycle_status == "resolved"
        others = (
            await session.scalars(select(AdoptionRequest).where(AdoptionRequest.post_id == post.id))
        ).all()
        assert sorted(row.status for row in others) == ["completed", "rejected"]
        assert (
            await session.scalar(
                select(func.count())
                .select_from(CommunityAuditLog)
                .where(
                    CommunityAuditLog.request_id == winners[0],
                    CommunityAuditLog.action == "adoption_complete",
                )
            )
            == 1
        )
        with pytest.raises(HTTPException):
            await service.adoption_action(session, winners[0], winner.user_id, withdraw=True)


@pytest.mark.asyncio
async def test_database_constraint_blocks_second_selected_applicant():
    factory = sessions()
    staff = await user(factory, "owner")
    post = await published(factory, staff)
    async with factory() as session:
        for _ in range(2):
            applicant = await user(factory)
            session.add(
                AdoptionRequest(
                    post_id=post.id,
                    user_id=applicant.id,
                    applicant_name="Test",
                    applicant_phone="0901234567",
                    applicant_address="Test address",
                    living_condition="Test living condition",
                    status="approved",
                )
            )
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_api_privacy_auth_totp_feed_and_feature_switch(monkeypatch):
    from app.core.database import engine
    from app.main import app

    factory = sessions()
    staff, author, stranger = [await user(factory, r) for r in ["owner", "customer", "customer"]]
    post = await published(factory, author, "found_pet")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        public = await client.get(f"/api/v1/community/posts/{post.slug}")
        assert public.status_code == 200, public.text
        assert "contact_phone" not in public.json()
        assert "0901234567" not in public.text
        assert "no-store" in public.headers["cache-control"]
        feed = await client.get("/api/v1/community/posts?limit=1")
        assert "items" in feed.json() and "next_cursor" in feed.json()
        assert (await client.get("/api/v1/community/posts?cursor=invalid")).status_code == 422
        assert (
            await client.post(f"/api/v1/community/posts/{post.slug}/contact-reveal")
        ).status_code == 401
        headers = {
            "Authorization": "Bearer "
            + create_access_token(subject=str(stranger.id), role="customer")
        }
        assert (
            await client.patch(
                f"/api/v1/community/posts/{post.id}",
                json={"version": 0, "title": "Không được sửa"},
                headers=headers,
            )
        ).status_code == 404
        contact = await client.post(
            f"/api/v1/community/posts/{post.slug}/contact-reveal", headers=headers
        )
        assert contact.status_code == 200 and contact.json()["contact_phone"] == "0901234567"
        staff_headers = {
            "Authorization": "Bearer " + create_access_token(subject=str(staff.id), role="owner")
        }
        denied = await client.post(
            f"/api/v1/admin/community/posts/{post.id}/moderate",
            json={"action": "hide", "reason": "Test"},
            headers=staff_headers,
        )
        assert denied.status_code == 403
        async with factory() as session:
            row = await service.owner_post(session, post.id, author.id, lock=True)
            await service.transition_lifecycle(
                session, row, "resolve", author.id, "Đã tìm được chủ"
            )
            await session.commit()
        assert (await client.get(f"/api/v1/community/posts/{post.slug}")).status_code == 200
        assert (
            await client.post(
                f"/api/v1/community/posts/{post.slug}/contact-reveal", headers=headers
            )
        ).status_code == 404
        monkeypatch.setenv("COMMUNITY_ENABLED", "false")
        get_settings.cache_clear()
        assert (await client.get("/api/v1/community/posts")).status_code == 503
        monkeypatch.setenv("COMMUNITY_ENABLED", "true")
        get_settings.cache_clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_worker_retries_expiry_retention_and_referenced_upload(monkeypatch):
    from app.worker import community_tasks as jobs

    factory = sessions()
    monkeypatch.setattr(jobs, "AsyncSessionLocal", factory)
    author = await user(factory)
    post = await published(factory, author, "lost_pet")
    async with factory() as session:
        row = await service.get_post(session, post.id, lock=True)
        row.expires_at = service.now() - timedelta(hours=1)
        await service.notify(
            session, author.id, "Unique notification", "/account/community", str(uuid.uuid4())
        )
        await session.commit()
    await jobs.maintain_community_posts({})
    await jobs.dispatch_community_outbox({})
    await jobs.dispatch_community_outbox({})
    async with factory() as session:
        assert (await service.get_post(session, post.id)).lifecycle_status == "expired"
        assert (
            await session.scalar(
                select(func.count())
                .select_from(CommunityNotification)
                .where(
                    CommunityNotification.user_id == author.id,
                    CommunityNotification.message == "Unique notification",
                )
            )
            == 1
        )
    await jobs.cleanup_community_data({})


def test_jwt_allows_small_clock_skew_but_rejects_future_tokens():
    import jwt

    near = create_access_token(
        subject=str(uuid.uuid4()),
        role="customer",
        extra={"iat": service.now() + timedelta(seconds=20)},
    )
    assert decode_token(near)["type"] == "access"
    far = create_access_token(
        subject=str(uuid.uuid4()),
        role="customer",
        extra={"iat": service.now() + timedelta(minutes=2)},
    )
    with pytest.raises(jwt.ImmatureSignatureError):
        decode_token(far)


def test_upload_metadata_mime_and_pixel_limits(monkeypatch):
    source = Image.new("RGB", (20, 10), "red")
    exif = Image.Exif()
    exif[270] = "PRIVATE LOCATION"
    raw = io.BytesIO()
    source.save(raw, "JPEG", exif=exif)
    cleaned, width, height = upload_service.transform_image(raw.getvalue(), "image/jpeg")
    assert (width, height) == (20, 10)
    assert not Image.open(io.BytesIO(cleaned)).getexif()
    with pytest.raises(HTTPException):
        upload_service.transform_image(raw.getvalue(), "image/png")
    monkeypatch.setattr(upload_service, "MAX_PIXELS", 100)
    with pytest.raises(HTTPException):
        upload_service.transform_image(raw.getvalue(), "image/jpeg")
    with pytest.raises(HTTPException):
        upload_service.get_image_path("../../private.jpg")


def test_forwarded_ip_only_from_configured_proxies(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "10.0.0.0/24")
    get_settings.cache_clear()

    def request(peer, value):
        return Request(
            {
                "type": "http",
                "client": (peer, 1234),
                "headers": [(b"x-forwarded-for", value.encode())],
            }
        )

    assert client_ip(request("203.0.113.4", "1.2.3.4")) == "203.0.113.4"
    assert client_ip(request("10.0.0.2", "9.9.9.9, 203.0.113.4")) == "203.0.113.4"
    assert client_ip(request("10.0.0.2", "invalid")) == "10.0.0.2"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_upload_cleanup_retains_attached_images_and_removes_orphans(monkeypatch):
    from starlette.datastructures import Headers, UploadFile

    from app.models.community import CommunityUpload
    from app.worker import community_tasks as jobs

    factory = sessions()
    monkeypatch.setattr(jobs, "AsyncSessionLocal", factory)
    author = await user(factory)
    raw = io.BytesIO()
    Image.new("RGB", (10, 10)).save(raw, "JPEG")
    async with factory() as session:
        uploads = []
        for _ in range(2):
            file = UploadFile(
                io.BytesIO(raw.getvalue()), headers=Headers({"content-type": "image/jpeg"})
            )
            item = await upload_service.process_and_save_upload(session, author.id, file)
            item.created_at = service.now() - timedelta(days=2)
            uploads.append(item)
        data = post_input().model_copy(update={"image_upload_ids": [uploads[0].id]})
        post = await service.create_post(session, author.id, data, str(uuid.uuid4()))
        await session.commit()
        assert len(schemas.CommunityPostOwnerOut.model_validate(post).images) == 1
        attached, orphan = uploads
    await jobs.cleanup_community_data({})
    async with factory() as session:
        assert await session.get(CommunityUpload, attached.id)
        assert await session.get(CommunityUpload, orphan.id) is None
        assert upload_service.get_image_path(attached.object_key).is_file()
        assert not upload_service.get_image_path(orphan.object_key).is_file()


@pytest.mark.asyncio
async def test_retention_and_recovering_outbox_lease(monkeypatch):
    from app.models.community import CommunityJobOutbox
    from app.worker import community_tasks as jobs

    factory = sessions()
    monkeypatch.setattr(jobs, "AsyncSessionLocal", factory)
    staff, applicant = await user(factory, "owner"), await user(factory)
    post = await published(factory, staff)
    async with factory() as session:
        row = AdoptionRequest(
            post_id=post.id,
            user_id=applicant.id,
            applicant_name="PRIVATE PERSON",
            applicant_phone="0901234567",
            applicant_address="PRIVATE ADDRESS",
            living_condition="PRIVATE CONDITIONS",
            admin_note="PRIVATE NOTE",
            status="rejected",
            updated_at=service.now() - timedelta(days=100),
        )
        session.add(row)
        job = CommunityJobOutbox(
            job_type="notification",
            unique_key=uuid.uuid4().hex,
            status="processing",
            locked_until=service.now() - timedelta(minutes=1),
            attempt_count=1,
            payload={
                "user_id": str(applicant.id),
                "message": "Recovered",
                "href": "/account/community",
            },
        )
        session.add(job)
        await session.commit()
        ident, key = row.id, job.unique_key
    await jobs.cleanup_community_data({})
    await jobs.dispatch_community_outbox({})
    await jobs.dispatch_community_outbox({})
    async with factory() as session:
        row = await session.get(AdoptionRequest, ident)
        assert (
            row.anonymized_at is not None and row.applicant_phone == "" and row.admin_note is None
        )
        assert "PRIVATE" not in str(service.adoption_out(row, admin=True))
        assert (
            await session.scalar(
                select(func.count())
                .select_from(CommunityNotification)
                .where(CommunityNotification.unique_key == key)
            )
            == 1
        )


@pytest.mark.asyncio
async def test_turnstile_fails_closed_without_production_secret(monkeypatch):
    from app.modules.community.guards import verify_turnstile

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("COMMUNITY_TURNSTILE_SECRET", "")
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as exc:
        await verify_turnstile(Request({"type": "http"}))
    assert exc.value.status_code == 503
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
