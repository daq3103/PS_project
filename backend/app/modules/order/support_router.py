"""Order-linked customer support. Authorization is checked on every ticket."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, has_staff_permission, require_cskh_or_owner
from app.core.rate_limit import enforce_rate_limit
from app.models.commerce import Order
from app.models.operations import SupportMessage, SupportTicket
from app.models.user import User

router = APIRouter(prefix="/api/v1", tags=["support"])


class TicketIn(BaseModel):
    order_id: UUID | None = None
    subject: str = Field(min_length=3, max_length=150)
    topic: Literal["order", "payment", "return", "other"] = "order"
    content: str = Field(min_length=10, max_length=5000)


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class TicketStatusIn(BaseModel):
    status: Literal["open", "in_progress", "waiting_customer", "closed"]


async def load_ticket(db, ticket_id, user, *, lock=False):
    stmt = select(SupportTicket).where(SupportTicket.id == ticket_id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    ticket = await db.scalar(stmt)
    if not ticket or (
        ticket.user_id != user.id and not has_staff_permission(user, "customer_support")
    ):
        raise HTTPException(404, "Không tìm thấy yêu cầu hỗ trợ.")
    return ticket


def ticket_dict(ticket):
    return {
        name: getattr(ticket, name)
        for name in ("id", "order_id", "subject", "topic", "status", "created_at", "updated_at")
    }


@router.post("/support/tickets", status_code=201)
async def create_ticket(
    body: TicketIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(key=f"rl:support:{user.id}", limit=5, window_seconds=3600)
    if body.order_id:
        order = await db.get(Order, body.order_id)
        if not order or order.user_id != user.id:
            raise HTTPException(404, "Không tìm thấy đơn hàng của bạn.")
    if not body.subject.strip() or not body.content.strip():
        raise HTTPException(422, "Vui lòng nhập tiêu đề và nội dung hỗ trợ.")
    ticket = SupportTicket(
        user_id=user.id, order_id=body.order_id, subject=body.subject.strip(), topic=body.topic
    )
    db.add(ticket)
    await db.flush()
    db.add(
        SupportMessage(
            ticket_id=ticket.id,
            user_id=user.id,
            author_type="customer",
            content=body.content.strip(),
        )
    )
    return ticket_dict(ticket)


@router.get("/support/tickets")
async def my_tickets(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    offset: int = Query(0, ge=0),
):
    tickets = (
        await db.scalars(
            select(SupportTicket)
            .where(SupportTicket.user_id == user.id)
            .order_by(SupportTicket.updated_at.desc(), SupportTicket.id)
            .offset(offset)
            .limit(50)
        )
    ).all()
    return [ticket_dict(t) for t in tickets]


@router.get("/admin/support/tickets")
async def staff_tickets(
    user: User = Depends(require_cskh_or_owner),
    db: AsyncSession = Depends(get_db),
    status: Literal["open", "in_progress", "waiting_customer", "closed"] | None = None,
    offset: int = Query(0, ge=0),
):
    stmt = (
        select(SupportTicket)
        .order_by(SupportTicket.updated_at.desc(), SupportTicket.id)
        .offset(offset)
        .limit(50)
    )
    if status:
        stmt = stmt.where(SupportTicket.status == status)
    return [ticket_dict(t) for t in (await db.scalars(stmt)).all()]


@router.get("/support/tickets/{ticket_id}")
async def ticket_detail(
    ticket_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    ticket = await load_ticket(db, ticket_id, user)
    rows = (
        await db.scalars(
            select(SupportMessage)
            .where(SupportMessage.ticket_id == ticket.id)
            .order_by(SupportMessage.created_at.desc(), SupportMessage.id.desc())
            .limit(200)
        )
    ).all()
    rows = list(reversed(rows))
    return {
        **ticket_dict(ticket),
        "messages": [
            {
                "id": m.id,
                "author_type": m.author_type,
                "content": m.content,
                "created_at": m.created_at,
            }
            for m in rows
        ],
    }


@router.post("/support/tickets/{ticket_id}/messages", status_code=201)
async def add_message(
    ticket_id: UUID,
    body: MessageIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(key=f"rl:support-reply:{user.id}", limit=30, window_seconds=60)
    ticket = await load_ticket(db, ticket_id, user, lock=True)
    if ticket.status == "closed":
        raise HTTPException(409, "Yêu cầu đã đóng. Vui lòng tạo yêu cầu mới nếu cần hỗ trợ thêm.")
    if not body.content.strip():
        raise HTTPException(422, "Vui lòng nhập nội dung.")
    staff = has_staff_permission(user, "customer_support") and ticket.user_id != user.id
    db.add(
        SupportMessage(
            ticket_id=ticket.id,
            user_id=user.id,
            author_type="staff" if staff else "customer",
            content=body.content.strip(),
        )
    )
    ticket.updated_at = datetime.now(UTC)
    ticket.status = "waiting_customer" if staff else "open"
    return {"status": "received"}


@router.patch("/admin/support/tickets/{ticket_id}")
async def update_ticket(
    ticket_id: UUID,
    body: TicketStatusIn,
    user: User = Depends(require_cskh_or_owner),
    db: AsyncSession = Depends(get_db),
):
    ticket = await load_ticket(db, ticket_id, user, lock=True)
    labels = {
        "open": "Mở",
        "in_progress": "Đang xử lý",
        "waiting_customer": "Chờ khách phản hồi",
        "closed": "Đã đóng",
    }
    if ticket.status != body.status:
        db.add(
            SupportMessage(
                ticket_id=ticket.id,
                user_id=user.id,
                author_type="system",
                content=f"Trạng thái: {labels[ticket.status]} → {labels[body.status]}",
            )
        )
        ticket.status = body.status
        ticket.updated_at = datetime.now(UTC)
    return ticket_dict(ticket)
