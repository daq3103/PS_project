"""Durable in-app notifications and rescue lifecycle maintenance."""

import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.community import (
    AdoptionRequest,
    CommunityJobOutbox,
    CommunityNotification,
    CommunityPost,
    CommunityPostImage,
    CommunityUpload,
)
from app.modules.community import service, upload_service

logger = logging.getLogger(__name__)


async def dispatch_community_outbox(ctx):
    if not get_settings().community_enabled:
        return {"disabled": True}
    moment = service.now()
    async with AsyncSessionLocal() as session:
        rows = (
            await session.scalars(
                select(CommunityJobOutbox)
                .where(
                    or_(
                        (CommunityJobOutbox.status == "pending")
                        & (CommunityJobOutbox.scheduled_at <= moment),
                        (CommunityJobOutbox.status == "processing")
                        & (CommunityJobOutbox.locked_until <= moment),
                    )
                )
                .order_by(CommunityJobOutbox.scheduled_at)
                .with_for_update(skip_locked=True)
                .limit(50)
            )
        ).all()
        ids = [row.id for row in rows]
        for row in rows:
            row.status = "processing"
            row.locked_until = moment + timedelta(minutes=5)
            row.attempt_count += 1
        await session.commit()
    done = 0
    for ident in ids:
        try:
            async with AsyncSessionLocal() as session:
                row = await session.get(CommunityJobOutbox, ident, with_for_update=True)
                if row.status == "done":
                    continue
                if row.job_type != "notification":
                    raise ValueError("Unknown job type")
                payload = row.payload
                await session.execute(
                    insert(CommunityNotification)
                    .values(
                        user_id=UUID(payload["user_id"]),
                        unique_key=row.unique_key or str(row.id),
                        message=payload["message"],
                        href=payload["href"],
                    )
                    .on_conflict_do_nothing(index_elements=["unique_key"])
                )
                row.status = "done"
                row.processed_at = service.now()
                row.locked_until = None
                row.last_error = None
                await session.commit()
                done += 1
        except Exception as exc:
            async with AsyncSessionLocal() as session:
                row = await session.get(CommunityJobOutbox, ident, with_for_update=True)
                row.last_error = type(exc).__name__  # no PII or payload in logs/errors
                row.locked_until = None
                row.status = "failed" if row.attempt_count >= 8 else "pending"
                row.scheduled_at = service.now() + timedelta(
                    seconds=min(3600, 30 * 2**row.attempt_count)
                )
                await session.commit()
            logger.warning("community_outbox_failed id=%s error=%s", ident, type(exc).__name__)
    return {"claimed": len(ids), "done": done}


async def maintain_community_posts(ctx):
    if not get_settings().community_enabled:
        return {"disabled": True}
    moment = service.now()
    expired = 0
    cursor = None
    while True:
        count, cursor, batch_expired = await _maintain_batch(moment, cursor)
        expired += batch_expired
        if count < 200:
            break
    return {"expired": expired}


async def _maintain_batch(moment, cursor):
    expired = 0
    async with AsyncSessionLocal() as session:
        posts = (
            await session.scalars(
                select(CommunityPost)
                .where(
                    CommunityPost.lifecycle_status == "open",
                    CommunityPost.expires_at <= moment + timedelta(days=3),
                    *([CommunityPost.id > cursor] if cursor else []),
                )
                .order_by(CommunityPost.id)
                .with_for_update(skip_locked=True)
                .limit(200)
            )
        ).all()
        for post in posts:
            active = post.post_type == "adoption" and await session.scalar(
                select(AdoptionRequest.id)
                .where(
                    AdoptionRequest.post_id == post.id,
                    AdoptionRequest.status.in_(service.ACTIVE_REQUESTS),
                )
                .limit(1)
            )
            if active:
                # Keep accepting workflow actions while staff reviews; never expire an active handover.
                await service.notify(
                    session,
                    post.author_user_id,
                    "Tin nhận nuôi cần kiểm tra lại hồ sơ đang xử lý.",
                    "/admin/community/adoptions",
                    f"review:{post.id}:{post.expires_at.date()}",
                )
                continue
            if post.expires_at <= moment:
                post.lifecycle_status = "expired"
                post.version += 1
                post.updated_at = moment
                await service.audit(session, post, None, "expire", "open", "expired")
                expired += 1
            else:
                await service.notify(
                    session,
                    post.author_user_id,
                    "Tin cứu hộ sắp hết hạn. Hãy xác nhận lại tình trạng.",
                    "/account/community",
                    f"expiry:{post.id}:{post.expires_at.isoformat()}",
                )
        await session.commit()
    return len(posts), posts[-1].id if posts else cursor, expired


async def cleanup_community_data(ctx):
    moment = service.now()
    removed = 0
    async with AsyncSessionLocal() as session:
        uploads = (
            await session.scalars(
                select(CommunityUpload)
                .where(
                    CommunityUpload.created_at < moment - timedelta(hours=24),
                    ~exists().where(CommunityPostImage.upload_id == CommunityUpload.id),
                )
                .order_by(CommunityUpload.id)
                .with_for_update(skip_locked=True)
                .limit(200)
            )
        ).all()
        for upload in uploads:
            # Recheck after acquiring the upload lock; a concurrent attach may have just committed.
            if await session.scalar(
                select(CommunityPostImage.id)
                .where(CommunityPostImage.upload_id == upload.id)
                .limit(1)
            ):
                continue
            upload_service.get_image_path(upload.object_key).unlink(missing_ok=True)
            await session.delete(upload)
            removed += 1
        cutoff = moment - timedelta(days=get_settings().community_retention_days)
        requests = (
            await session.scalars(
                select(AdoptionRequest)
                .where(
                    AdoptionRequest.status.in_(("completed", "rejected", "withdrawn")),
                    AdoptionRequest.updated_at < cutoff,
                    AdoptionRequest.anonymized_at.is_(None),
                )
                .with_for_update(skip_locked=True)
                .limit(200)
            )
        ).all()
        for row in requests:
            row.applicant_name = "Đã ẩn danh"
            row.applicant_phone = ""
            row.applicant_address = "Đã xóa"
            row.living_condition = "Đã xóa"
            row.admin_note = None
            row.outcome_reason = None
            row.anonymized_at = moment
        await session.commit()
        # Recover files left behind by process failure before upload transaction commit.
        known = set((await session.scalars(select(CommunityUpload.object_key))).all())
    for path in upload_service._upload_dir().glob("*.jpg"):
        if (
            path.name not in known
            and path.stat().st_mtime < (moment - timedelta(hours=24)).timestamp()
        ):
            path.unlink(missing_ok=True)
    return {"removed_uploads": removed, "anonymized_requests": len(requests)}
