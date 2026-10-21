"""Rescue operations: role dependency plus /admin TOTP middleware."""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.community import (
    AdoptionRequest,
    CommunityAuditLog,
    CommunityJobOutbox,
    CommunityPost,
    CommunityReport,
)
from app.models.user import User
from app.modules.community import schemas, service
from app.modules.community.permissions import require_cskh_or_owner

router = APIRouter(
    prefix="/api/v1/admin/community",
    tags=["admin-community"],
    dependencies=[Depends(require_cskh_or_owner)],
)


async def admin_out(session, post):
    data = schemas.CommunityPostAdminOut.model_validate(post).model_dump()
    author = await session.get(User, post.author_user_id)
    data.update(
        author_name=author.full_name if author else "",
        author_contact=(author.email or author.phone) if author else None,
    )
    return data


@router.get("/posts", response_model=list[schemas.CommunityPostAdminOut])
async def posts(qs: schemas.AdminListQs = Depends(), session: AsyncSession = Depends(get_db)):
    rows, _ = await service.admin_list_posts(session, qs)
    return [await admin_out(session, r) for r in rows]


@router.get("/posts/{post_id}", response_model=schemas.CommunityPostAdminOut)
async def detail(post_id: UUID, session: AsyncSession = Depends(get_db)):
    return await admin_out(session, await service.get_post(session, post_id))


@router.post("/posts", response_model=schemas.CommunityPostAdminOut, status_code=201)
async def create(
    body: schemas.CommunityPostCreateIn,
    idempotency_key: str = Header(min_length=8, max_length=100),
    user: User = Depends(require_cskh_or_owner),
    session: AsyncSession = Depends(get_db),
):
    post = await service.create_post(session, user.id, body, idempotency_key, adoption=True)
    await session.commit()
    return await admin_out(session, post)


@router.post("/posts/{post_id}/moderate", response_model=schemas.CommunityPostAdminOut)
async def moderate(
    post_id: UUID,
    body: schemas.ModerationActionIn,
    user: User = Depends(require_cskh_or_owner),
    session: AsyncSession = Depends(get_db),
):
    post = await service.get_post(session, post_id, lock=True)
    await service.admin_moderate(session, post, body.action, user.id, body.reason, body.version)
    await session.commit()
    return await admin_out(session, post)


@router.patch("/posts/{post_id}", response_model=schemas.CommunityPostAdminOut)
async def edit(
    post_id: UUID,
    body: schemas.CommunityPostUpdateIn,
    user: User = Depends(require_cskh_or_owner),
    session: AsyncSession = Depends(get_db),
):
    post = await service.get_post(session, post_id, lock=True)
    await service.update_post(session, post, user.id, body)
    await session.commit()
    return await admin_out(session, post)


@router.post("/posts/{post_id}/lifecycle", response_model=schemas.CommunityPostAdminOut)
async def lifecycle(
    post_id: UUID,
    body: schemas.LifecycleActionIn,
    user: User = Depends(require_cskh_or_owner),
    session: AsyncSession = Depends(get_db),
):
    post = await service.get_post(session, post_id, lock=True)
    await service.transition_lifecycle(
        session, post, body.action, user.id, body.reason, body.version
    )
    await session.commit()
    return await admin_out(session, post)


@router.get("/posts/{post_id}/audit", response_model=list[schemas.AuditLogOut])
async def history(post_id: UUID, session: AsyncSession = Depends(get_db)):
    return (
        await session.scalars(
            select(CommunityAuditLog)
            .where(CommunityAuditLog.post_id == post_id)
            .order_by(CommunityAuditLog.created_at.desc())
            .limit(200)
        )
    ).all()


@router.get("/reports", response_model=list[schemas.ReportOut])
async def reports(
    status: schemas.REPORT_STATUS | None = None,
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    query = select(CommunityReport)
    if status:
        query = query.where(CommunityReport.status == status)
    return (
        await session.scalars(
            query.order_by(CommunityReport.created_at.desc()).offset(offset).limit(100)
        )
    ).all()


@router.post("/reports/{report_id}/handle", response_model=schemas.ReportOut)
async def handle_report(
    report_id: UUID,
    body: schemas.ReportHandleIn,
    user: User = Depends(require_cskh_or_owner),
    session: AsyncSession = Depends(get_db),
):
    row = await service.admin_handle_report(session, report_id, body, user.id)
    await session.commit()
    return row


@router.get("/adoption-requests", response_model=list[schemas.AdoptionAdminOut])
async def applications(
    status: schemas.ADOPTION_STATUS | None = None,
    post_id: UUID | None = None,
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    query = select(AdoptionRequest)
    if status:
        query = query.where(AdoptionRequest.status == status)
    if post_id:
        query = query.where(AdoptionRequest.post_id == post_id)
    rows = (
        await session.scalars(
            query.order_by(AdoptionRequest.created_at.desc()).offset(offset).limit(100)
        )
    ).all()
    return [service.adoption_out(r, admin=True) for r in rows]


@router.post("/adoption-requests/{request_id}/action", response_model=schemas.AdoptionAdminOut)
async def action(
    request_id: UUID,
    body: schemas.AdoptionActionIn,
    user: User = Depends(require_cskh_or_owner),
    session: AsyncSession = Depends(get_db),
):
    row = await service.adoption_action(session, request_id, user.id, body)
    await session.commit()
    return service.adoption_out(row, admin=True)


@router.get("/metrics")
async def metrics(session: AsyncSession = Depends(get_db)):
    async def count(model, *where):
        return await session.scalar(select(func.count()).select_from(model).where(*where))

    return {
        "pending_posts": await count(CommunityPost, CommunityPost.moderation_status == "pending"),
        "oldest_pending_at": await session.scalar(
            select(func.min(CommunityPost.created_at)).where(
                CommunityPost.moderation_status == "pending"
            )
        ),
        "pending_reports": await count(CommunityReport, CommunityReport.status == "pending"),
        "active_applications": await count(
            AdoptionRequest, AdoptionRequest.status.in_(service.ACTIVE_REQUESTS)
        ),
        "completed_adoptions": await count(AdoptionRequest, AdoptionRequest.status == "completed"),
        "resolved_posts": await count(CommunityPost, CommunityPost.lifecycle_status == "resolved"),
        "pending_jobs": await count(
            CommunityJobOutbox, CommunityJobOutbox.status.in_(("pending", "processing"))
        ),
        "failed_jobs": await count(CommunityJobOutbox, CommunityJobOutbox.status == "failed"),
    }
