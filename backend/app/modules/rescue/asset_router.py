"""Images and scanned evidence: sanitize pixels, authorize every read, no public upload folder."""

import secrets
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, has_staff_permission
from app.core.rate_limit import enforce_rate_limit
from app.models.rescue import RescueAnimal, RescueReport
from app.models.rescue_workflow import RescueAsset, RescuePartner
from app.models.user import User
from app.modules.community.upload_service import FORMATS, transform_image
from app.modules.rescue import service as svc
from app.modules.rescue import workflow_service as ws
from app.modules.rescue.router import manage

router = APIRouter(prefix="/api/v1", tags=["rescue-evidence"])


def asset_path(key):
    import re

    if not re.fullmatch(r"[A-Za-z0-9_-]{32}\.jpg", key):
        svc.fail("Không tìm thấy ảnh.", status=404)
    return Path(get_settings().community_upload_dir) / "rescue-evidence" / key


async def authorize(db, user, kind, ident, write=False):
    if kind == "fund":
        from app.models.rescue import RescueFund

        if not has_staff_permission(user, "rescue_finance") or not await db.get(RescueFund, ident):
            svc.fail("Không tìm thấy chứng từ trong phạm vi của bạn.", status=404)
    elif kind == "care":
        await svc.animal(db, ident, user, lock=False)
    elif kind == "animal":
        if write and not svc.manager(user):
            svc.fail("Cần điều phối xác nhận ảnh hồ sơ bé.", "PERMISSION_DENIED", 403)
        await svc.animal(db, ident, user, lock=False)
    elif kind == "report":
        row = await db.get(RescueReport, ident)
        if not row or (
            not svc.manager(user) and row.user_id != user.id and row.assignee_id != user.id
        ):
            svc.fail("Không tìm thấy tin trong phạm vi của bạn.", status=404)
    elif kind == "application":
        await ws.application(db, ident, user)
    elif kind == "partner":
        row = await db.get(RescuePartner, ident)
        if not row or (not svc.manager(user) and row.user_id != user.id):
            svc.fail("Không tìm thấy đăng ký trong phạm vi của bạn.", status=404)
    else:
        svc.fail("Loại hồ sơ không phù hợp.", status=422)


@router.post("/rescue/files", status_code=201)
async def upload(
    resource_kind: str = Form(),
    resource_id: UUID = Form(),
    caption: str = Form(""),
    file: UploadFile = File(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        key="rescue:file-upload:" + str(user.id), limit=20, window_seconds=3600
    )
    await authorize(db, user, resource_kind, resource_id, True)
    if len(caption) > 200:
        svc.fail("Chú thích tối đa 200 ký tự.", status=422)
    await ws.lock(db, f"files:{resource_kind}:{resource_id}")
    if (
        await db.scalar(
            select(func.count())
            .select_from(RescueAsset)
            .where(
                RescueAsset.resource_kind == resource_kind,
                RescueAsset.resource_id == resource_id,
                RescueAsset.deleted_at.is_(None),
            )
        )
        >= 20
    ):
        svc.fail("Mỗi hồ sơ tối đa 20 ảnh hoặc bản chụp giấy tờ.")
    maximum = get_settings().max_community_upload_bytes
    raw = await file.read(maximum + 1)
    if len(raw) > maximum:
        svc.fail("Ảnh vượt giới hạn 5 MB.", status=413)
    if file.content_type not in FORMATS:
        svc.fail("Dùng ảnh JPEG, PNG hoặc WebP; giấy tờ có thể gửi dưới dạng bản chụp.", status=422)
    clean, _, _ = await run_in_threadpool(transform_image, raw, file.content_type)
    key = secrets.token_urlsafe(24) + ".jpg"
    path = asset_path(key)
    await run_in_threadpool(path.parent.mkdir, parents=True, exist_ok=True)
    await run_in_threadpool(path.write_bytes, clean)
    row = RescueAsset(
        resource_kind=resource_kind,
        resource_id=resource_id,
        uploader_id=user.id,
        storage_key=key,
        media_type="image/jpeg",
        size=len(clean),
        caption=caption,
    )
    db.add(row)
    try:
        await db.flush()
    except Exception:
        await run_in_threadpool(path.unlink, missing_ok=True)
        raise
    svc.audit(db, user, row.id, "asset_upload", resource_kind=resource_kind, parent_id=resource_id)
    return {"id": row.id, "caption": caption, "public": False}


@router.get("/rescue/files")
async def files(
    resource_kind: str,
    resource_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await authorize(db, user, resource_kind, resource_id)
    rows = (
        await db.scalars(
            select(RescueAsset)
            .where(
                RescueAsset.resource_kind == resource_kind,
                RescueAsset.resource_id == resource_id,
                RescueAsset.deleted_at.is_(None),
            )
            .order_by(RescueAsset.created_at)
        )
    ).all()
    result = []
    for row in rows:
        ticket = jwt.encode(
            {
                "type": "rescue-file",
                "sub": str(user.id),
                "asset": str(row.id),
                "exp": svc.now() + timedelta(minutes=5),
            },
            get_settings().jwt_secret,
            algorithm="HS256",
        )
        result.append(
            {
                "id": row.id,
                "caption": row.caption,
                "public": row.public,
                "publication_allowed": row.publication_allowed,
                "url": f"/api/proxy/api/v1/rescue/files/{row.id}/download?ticket={ticket}",
            }
        )
    return result


@router.get("/rescue/files/{ident}/download")
async def download(
    ident: UUID,
    ticket: str = Query(max_length=1000),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        claims = jwt.decode(
            ticket,
            get_settings().jwt_secret,
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
        if (
            claims.get("type") != "rescue-file"
            or claims["sub"] != str(user.id)
            or claims.get("asset") != str(ident)
        ):
            raise ValueError("Invalid file scope")
    except (jwt.PyJWTError, ValueError):
        svc.fail("Liên kết xem ảnh đã hết hạn. Vui lòng tải lại hồ sơ.", status=403)
    row = await db.get(RescueAsset, ident)
    if not row or row.deleted_at:
        svc.fail("Ảnh không còn khả dụng.", status=404)
    await authorize(db, user, row.resource_kind, row.resource_id)
    path = asset_path(row.storage_key)
    if not path.is_file():
        svc.fail("Ảnh chưa sẵn sàng. Vui lòng liên hệ trạm.", status=404)
    return FileResponse(
        path,
        media_type="image/jpeg",
        filename="ho-so.jpg",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.post("/admin/rescue/files/{ident}/publish")
async def publish(
    ident: UUID,
    rights_confirmed: bool = Query(),
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    row = await db.scalar(select(RescueAsset).where(RescueAsset.id == ident).with_for_update())
    if not row or row.deleted_at or row.resource_kind not in ("animal", "fund"):
        svc.fail("Không công bố giấy tờ của người báo hoặc người nhận nuôi.", status=422)
    if not rights_confirmed:
        svc.fail(
            "Cần kiểm tra quyền dùng ảnh và che thông tin riêng trước khi công bố.", status=422
        )
    if row.resource_kind == "animal":
        a = await db.get(RescueAnimal, row.resource_id)
        if not a or not a.publication:
            svc.fail("Cần duyệt hồ sơ bé trước khi công bố ảnh.")
    else:
        from app.models.rescue import RescueFund

        f = await db.get(RescueFund, row.resource_id)
        if not has_staff_permission(user, "platform_manage") or not f or not f.public_report:
            svc.fail(
                "Chủ trạm duyệt báo cáo và bản chứng từ đã che thông tin trước khi công bố.",
                status=403,
            )
    if row.uploader_id != user.id and row.resource_kind != "fund":
        from app.models.rescue_workflow import RescueConsent

        if not await db.scalar(
            select(RescueConsent.id).where(
                RescueConsent.user_id == row.uploader_id,
                RescueConsent.resource_id == row.id,
                RescueConsent.purpose == "media",
                RescueConsent.allowed.is_(True),
            )
        ):
            svc.fail("Cần người gửi ảnh đồng ý quyền công bố trước.")
    row.publication_allowed, row.public = True, True
    svc.audit(db, user, row.id, "asset_publish", rights_confirmed=True)
    return {"public": True}


@router.delete("/rescue/files/{ident}")
async def remove(
    ident: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    row = await db.scalar(select(RescueAsset).where(RescueAsset.id == ident).with_for_update())
    if not row or (row.uploader_id != user.id and not svc.manager(user)):
        svc.fail("Không tìm thấy ảnh thuộc quyền của bạn.", status=404)
    if row.resource_kind == "fund":
        await authorize(db, user, "fund", row.resource_id)
        row.public, row.publication_allowed = False, False
    else:
        row.public, row.publication_allowed, row.deleted_at = False, False, svc.now()
    svc.audit(db, user, row.id, "asset_withdraw")
    # Tombstone immediately; housekeeping removes bytes after commit, not during a rollback.
    return {"deleted": True}


@router.get("/rescue/public-images/{ident}")
async def public_image(ident: UUID, db: AsyncSession = Depends(get_db)):
    row = await db.get(RescueAsset, ident)
    if (
        not row
        or not row.public
        or not row.publication_allowed
        or row.deleted_at
        or row.resource_kind not in ("animal", "fund")
    ):
        svc.fail("Không tìm thấy ảnh công khai.", status=404)
    if row.resource_kind == "animal":
        animal = await db.get(RescueAnimal, row.resource_id)
        if not animal or not animal.publication:
            svc.fail("Hồ sơ chưa được công bố.", status=404)
    else:
        from app.models.rescue import RescueFund

        fund = await db.get(RescueFund, row.resource_id)
        if not fund or not fund.public_report:
            svc.fail("Báo cáo chưa được công bố.", status=404)
    path = asset_path(row.storage_key)
    if not path.is_file():
        svc.fail("Không tìm thấy ảnh.", status=404)
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
