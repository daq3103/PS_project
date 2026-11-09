"""Bounded, private local uploads shared with the worker via a Docker volume."""

import io
import re
import secrets
import warnings
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.deps import has_staff_permission
from app.models.community import CommunityPost, CommunityPostImage, CommunityUpload

MAX_PIXELS = 20_000_000
MAX_DIMENSION = 1600
FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


def _upload_dir():
    path = Path(get_settings().community_upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_image_path(key):
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,60}\.jpg", key):
        raise HTTPException(404, "Không tìm thấy ảnh")
    return _upload_dir() / key


def transform_image(raw, content_type):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as probe:
                if (
                    probe.format != FORMATS.get(content_type)
                    or probe.width * probe.height > MAX_PIXELS
                ):
                    raise ValueError("Định dạng hoặc kích thước ảnh không hợp lệ")
                probe.verify()
            with Image.open(io.BytesIO(raw)) as source:
                oriented = ImageOps.exif_transpose(source)
                oriented.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
                rgb = oriented.convert("RGB")
                # Fresh pixel buffer drops EXIF, ICC, comments and other source metadata.
                clean = Image.new("RGB", rgb.size)
                clean.paste(rgb)
                output = io.BytesIO()
                clean.save(output, "JPEG", quality=85)
                return output.getvalue(), clean.width, clean.height
    except (
        ValueError,
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise HTTPException(422, "Ảnh không hợp lệ, sai định dạng hoặc quá nhiều điểm ảnh") from exc


async def process_and_save_upload(session, user_id, file):
    maximum = get_settings().max_community_upload_bytes
    raw = await file.read(maximum + 1)
    if len(raw) > maximum:
        raise HTTPException(413, "Ảnh vượt quá 5 MB")
    if file.content_type not in FORMATS:
        raise HTTPException(422, "Chỉ nhận JPEG, PNG hoặc WebP")
    data, width, height = await run_in_threadpool(transform_image, raw, file.content_type)
    key = secrets.token_urlsafe(24) + ".jpg"
    path = get_image_path(key)
    await run_in_threadpool(path.write_bytes, data)
    row = CommunityUpload(
        uploader_user_id=user_id,
        object_key=key,
        original_filename=None,
        content_type="image/jpeg",
        size_bytes=len(data),
        width=width,
        height=height,
        status="ready",
    )
    session.add(row)
    try:
        await session.flush()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return row


async def can_view_upload(session, key, user):
    upload = await session.scalar(
        select(CommunityUpload).where(
            CommunityUpload.object_key == key, CommunityUpload.status == "ready"
        )
    )
    if not upload:
        return False
    if user and (upload.uploader_user_id == user.id or has_staff_permission(user, "rescue_manage")):
        return True
    # Approved summaries can retain photos after resolution; hidden/pending photos are private.
    return (
        await session.scalar(
            select(CommunityPostImage.id)
            .join(CommunityPost)
            .where(
                CommunityPostImage.upload_id == upload.id,
                CommunityPost.moderation_status == "approved",
            )
            .limit(1)
        )
        is not None
    )
