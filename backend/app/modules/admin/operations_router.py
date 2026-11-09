from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_platform_manager
from app.models.commerce import Order
from app.models.operations import CommerceJob, OperationCase
from app.models.user import User

router = APIRouter(
    prefix="/api/v1/admin/operations", tags=["operations"], dependencies=[Depends(require_platform_manager)]
)


@router.get("")
async def operations(db: AsyncSession = Depends(get_db)):
    jobs = (
        await db.scalars(
            select(CommerceJob)
            .where(CommerceJob.status != "completed")
            .order_by(CommerceJob.created_at)
            .limit(100)
        )
    ).all()
    cases = (
        await db.execute(
            select(OperationCase, Order.order_code)
            .join(Order, Order.id == OperationCase.order_id)
            .where(OperationCase.status == "open")
            .order_by(OperationCase.created_at)
            .limit(100)
        )
    ).all()
    return {
        "jobs": [
            {
                "id": j.id,
                "task": j.task,
                "status": j.status,
                "attempts": j.attempts,
                "last_error": j.last_error,
                "created_at": j.created_at,
            }
            for j in jobs
        ],
        "cases": [
            {
                "id": c.id,
                "order_code": code,
                "kind": c.kind,
                "amount": c.amount,
                "status": c.status,
                "created_at": c.created_at,
            }
            for c, code in cases
        ],
    }


@router.post("/jobs/{job_id}/retry")
async def retry_job(
    job_id: UUID, owner: User = Depends(require_platform_manager), db: AsyncSession = Depends(get_db)
):
    job = await db.scalar(select(CommerceJob).where(CommerceJob.id == job_id).with_for_update())
    if not job or job.status != "failed":
        raise HTTPException(409, "Tác vụ chưa ở trạng thái cần chạy lại.")
    job.status, job.attempts, job.next_attempt_at = "pending", 0, datetime.now(UTC)
    job.result = {"retried_by": str(owner.id), "retried_at": datetime.now(UTC).isoformat()}
    return {"status": "pending"}


class ResolveIn(BaseModel):
    reference: str = Field(min_length=6, max_length=150)
    note: str = Field(min_length=10, max_length=2000)


@router.post("/cases/{case_id}/resolve")
async def resolve_case(
    case_id: UUID,
    body: ResolveIn,
    owner: User = Depends(require_platform_manager),
    db: AsyncSession = Depends(get_db),
):
    initial = await db.get(OperationCase, case_id)
    if not initial:
        raise HTTPException(404, "Không tìm thấy vụ việc.")
    await db.execute(select(Order.id).where(Order.id == initial.order_id).with_for_update())
    case = await db.scalar(
        select(OperationCase)
        .where(OperationCase.id == case_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not case or case.status != "open":
        raise HTTPException(409, "Vụ việc không còn ở trạng thái chờ xử lý.")
    duplicate = await db.scalar(
        select(OperationCase.id).where(OperationCase.resolution_reference == body.reference.strip())
    )
    if duplicate:
        raise HTTPException(409, "Chứng từ này đã được ghi nhận cho một vụ việc khác.")
    if len(body.reference.strip()) < 6 or len(body.note.strip()) < 10:
        raise HTTPException(422, "Vui lòng nhập đầy đủ mã chứng từ và nội dung xử lý.")
    case.status, case.resolved_by, case.resolved_at = "resolved", owner.id, datetime.now(UTC)
    case.resolution_reference, case.note = body.reference.strip(), body.note.strip()
    # A completed manual refund is recorded as an obligation resolution, not a fabricated provider callback.
    return {"status": "resolved"}
