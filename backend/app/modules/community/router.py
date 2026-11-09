"""Public and authenticated self-service rescue endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, get_current_user_optional
from app.models.community import AdoptionRequest, CommunityNotification
from app.models.user import User
from app.modules.community import schemas, service, upload_service
from app.modules.community.guards import limit, verify_turnstile
from app.modules.community.locations import CATALOG

router = APIRouter(prefix="/api/v1/community", tags=["community"])


@router.get("/config")
async def config():
    settings = get_settings()
    return {
        "enabled": settings.community_enabled,
        "turnstile_site_key": settings.community_turnstile_site_key,
    }


@router.get("/locations")
async def locations():
    return CATALOG


@router.get("/pet-options")
async def pet_options():
    from app.modules.community.pet_traits import pet_options as catalog

    return catalog()


@router.get("/posts", response_model=schemas.CommunityFeedOut)
async def list_posts(
    filters: Annotated[schemas.CommunityFeedQs, Query()], session: AsyncSession = Depends(get_db)
):
    items, cursor = await service.list_public_posts(session, filters)
    return {"items": items, "next_cursor": cursor}


@router.get("/posts/{slug}", response_model=schemas.CommunityPostPublicOut)
async def get_post(slug: str, session: AsyncSession = Depends(get_db)):
    post = await service.get_public_post_by_slug(session, slug)
    if not post:
        raise HTTPException(404, "Không tìm thấy tin")
    return post


@router.post("/posts/{slug}/contact-reveal", response_model=schemas.ContactRevealOut)
async def reveal_contact(
    slug: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await limit(request, user.id, "contact", 10, 600)
    result = await service.reveal_contact(session, slug, user.id)
    await session.commit()
    return result


@router.post(
    "/posts",
    response_model=schemas.CommunityPostOwnerOut,
    status_code=201,
    dependencies=[Depends(verify_turnstile)],
)
async def create_post(
    body: schemas.CommunityPostCreateIn,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await limit(request, user.id, "post", 3)
    post = await service.create_post(session, user.id, body, idempotency_key)
    await session.commit()
    return post


@router.get("/me/posts", response_model=list[schemas.CommunityPostOwnerOut])
async def my_posts(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    return await service.list_my_posts(session, user.id)


@router.get("/me/posts/{post_id}", response_model=schemas.CommunityPostOwnerOut)
async def my_post(
    post_id: UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
):
    return await service.owner_post(session, post_id, user.id)


@router.patch("/posts/{post_id}", response_model=schemas.CommunityPostOwnerOut)
async def update_post(
    post_id: UUID,
    body: schemas.CommunityPostUpdateIn,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await limit(request, user.id, "edit", 10)
    post = await service.owner_post(session, post_id, user.id, lock=True)
    if post.post_type == "adoption":
        raise HTTPException(403, "Sửa tin nhận nuôi trong trang quản trị")
    result = await service.update_post(session, post, user.id, body)
    await session.commit()
    return result


@router.post("/posts/{post_id}/lifecycle", response_model=schemas.CommunityPostOwnerOut)
async def transition(
    post_id: UUID,
    body: schemas.LifecycleActionIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    # Only owner actions here. Staff acting on other users' posts must use the TOTP-protected admin route.
    post = await service.owner_post(session, post_id, user.id, lock=True)
    if post.post_type == "adoption":
        raise HTTPException(403, "Quản lý tin nhận nuôi trong trang quản trị")
    result = await service.transition_lifecycle(
        session, post, body.action, user.id, body.reason, body.version
    )
    await session.commit()
    return result


@router.post("/posts/{post_id}/reports", response_model=schemas.ReportOut, status_code=201)
async def report(
    post_id: UUID,
    body: schemas.ReportIn,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await limit(request, user.id, "report", 5)
    result = await service.report_post(session, post_id, user.id, body.reason)
    await session.commit()
    return result


@router.post("/uploads")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await limit(request, user.id, "upload", 20)
    result = await upload_service.process_and_save_upload(session, user.id, file)
    await session.commit()
    return {
        "upload_id": str(result.id),
        "object_key": result.object_key,
        "url": f"/api/proxy/api/v1/community/uploads/{result.object_key}",
    }


@router.get("/uploads/{object_key}")
async def get_upload(
    object_key: str,
    user: User | None = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_db),
):
    if not await upload_service.can_view_upload(session, object_key, user):
        raise HTTPException(404, "Không tìm thấy ảnh")
    path = upload_service.get_image_path(object_key)
    if not path.is_file():
        raise HTTPException(404, "Không tìm thấy ảnh")
    return FileResponse(
        path, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"}
    )


@router.post(
    "/posts/{post_id}/adoption-requests", response_model=schemas.AdoptionOut, status_code=201
)
async def apply(
    post_id: UUID,
    body: schemas.AdoptionCreateIn,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await limit(request, user.id, "apply", 5)
    row = await service.create_adoption_request(session, post_id, user.id, body, idempotency_key)
    await session.commit()
    return service.adoption_out(row)


@router.get("/me/adoption-requests", response_model=list[schemas.AdoptionOut])
async def applications(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
):
    rows = (
        await session.scalars(
            select(AdoptionRequest)
            .where(AdoptionRequest.user_id == user.id)
            .order_by(AdoptionRequest.created_at.desc())
            .limit(200)
        )
    ).all()
    return [service.adoption_out(row) for row in rows]


@router.post("/adoption-requests/{request_id}/withdraw", response_model=schemas.AdoptionOut)
async def withdraw(
    request_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    row = await service.adoption_action(session, request_id, user.id, withdraw=True)
    await session.commit()
    return service.adoption_out(row)


@router.get("/me/notifications", response_model=list[schemas.NotificationOut])
async def notifications(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
):
    return (
        await session.scalars(
            select(CommunityNotification)
            .where(CommunityNotification.user_id == user.id)
            .order_by(CommunityNotification.created_at.desc())
            .limit(100)
        )
    ).all()


@router.post("/me/notifications/{notification_id}/read", status_code=204)
async def mark_read(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    row = await session.get(CommunityNotification, notification_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Không tìm thấy thông báo")
    row.read_at = service.now()
    await session.commit()
