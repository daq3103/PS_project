from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rate_limit import enforce_rate_limit
from app.models.rescue import RescueReport
from app.models.rescue_workflow import RescueMessage, RescuePartner
from app.models.user import User
from app.modules.rescue import service as svc
from app.modules.rescue import workflow_schemas as s
from app.modules.rescue import workflow_service as ws
from app.modules.rescue.router import mutate

router = APIRouter(prefix="/api/v1", tags=["rescue-conversations"])


async def authorize(db, user, kind, ident):
    if kind == "support":
        if not await db.get(User, ident) or (ident != user.id and not svc.manager(user)):
            svc.fail("Không tìm thấy cuộc trao đổi của bạn.", status=404)
        return ident
    if kind == "application":
        return (await ws.application(db, ident, user)).user_id
    if kind == "report":
        row = await db.get(RescueReport, ident)
        if not row or (not svc.manager(user) and user.id not in (row.user_id, row.assignee_id)):
            svc.fail("Không tìm thấy cuộc trao đổi trong phạm vi của bạn.", status=404)
        return row.user_id
    if kind == "partner":
        row = await db.get(RescuePartner, ident)
        if not row or (not svc.manager(user) and row.user_id != user.id):
            svc.fail("Không tìm thấy đăng ký của bạn.", status=404)
        return row.user_id
    svc.fail("Loại trao đổi không phù hợp.", status=422)


@router.get("/rescue/messages")
async def messages(
    resource_kind: str,
    resource_id: UUID,
    before: UUID | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await authorize(db, user, resource_kind, resource_id)
    stmt = (
        select(RescueMessage, User.full_name)
        .join(User, User.id == RescueMessage.sender_id)
        .where(
            RescueMessage.resource_kind == resource_kind, RescueMessage.resource_id == resource_id
        )
    )
    if before:
        boundary = await db.get(RescueMessage, before)
        if (
            not boundary
            or boundary.resource_kind != resource_kind
            or boundary.resource_id != resource_id
        ):
            svc.fail("Mốc tin nhắn không hợp lệ.", status=422)
        stmt = stmt.where(RescueMessage.created_at < boundary.created_at)
    rows = (
        await db.execute(
            stmt.order_by(RescueMessage.created_at.desc(), RescueMessage.id).limit(100)
        )
    ).all()
    return [
        {
            "id": r.id,
            "body": r.body,
            "created_at": r.created_at,
            "sender_name": name,
            "mine": r.sender_id == user.id,
        }
        for r, name in reversed(rows)
    ]


@router.post("/rescue/messages", status_code=201)
async def send(
    body: s.MessageIn,
    request: Request,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    recipient = await authorize(db, user, body.resource_kind, body.resource_id)
    await enforce_rate_limit(key="rescue:message:" + str(user.id), limit=40, window_seconds=3600)

    async def create():
        row = RescueMessage(**body.model_dump(), sender_id=user.id)
        db.add(row)
        await db.flush()
        from app.modules.community.service import notify

        if svc.manager(user):
            recipients = [recipient] if recipient and recipient != user.id else []
        else:
            from sqlalchemy import or_

            recipients = (
                await db.scalars(
                    select(User.id).where(
                        User.is_active.is_(True),
                        or_(
                            User.role == "owner", User.staff_permissions.contains(["rescue_manage"]), User.staff_permissions.contains(["platform_manage"])
                        ),
                    )
                )
            ).all()
        for ident in recipients:
            await notify(
                db,
                ident,
                "Bạn có lời nhắn mới trong phần trao đổi với trạm.",
                "/account/rescue" if ident == recipient else "/admin/rescue/coordination",
                f"rescue-message:{row.id}:{ident}",
            )
        return {"id": str(row.id), "created_at": row.created_at}

    return await mutate(db, user, "message", key, body, create)
