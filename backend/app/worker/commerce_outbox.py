"""Execute durable DB jobs with a lease. Redis loss cannot erase outstanding work."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.database import AsyncSessionLocal
from app.models.operations import CommerceJob


async def record_job(session, task: str, reference: str, payload: dict):
    await session.execute(
        insert(CommerceJob)
        .values(
            business_key=f"{task}:{reference}",
            task=task,
            payload=payload,
            status="pending",
            attempts=0,
        )
        .on_conflict_do_nothing(index_elements=["business_key"])
    )


async def dispatch_commerce_jobs(ctx: dict):
    from app.worker.tasks import (
        create_shipment_job,
        create_vietqr_payment_job,
        send_order_confirmation_email,
    )

    handlers = {
        "create_vietqr_payment": create_vietqr_payment_job,
        "send_order_confirmation_email": send_order_confirmation_email,
        "create_shipment": create_shipment_job,
    }
    count = 0
    for _ in range(3):
        now = datetime.now(UTC)
        async with AsyncSessionLocal() as db:
            job = await db.scalar(
                select(CommerceJob)
                .where(
                    or_(
                        and_(CommerceJob.status == "pending", CommerceJob.next_attempt_at <= now),
                        and_(CommerceJob.status == "running", CommerceJob.lease_until < now),
                    )
                )
                .order_by(CommerceJob.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if not job:
                break
            if job.status == "running" and job.attempts >= 5:
                job.status = "failed"
                job.last_error = "lease_exhausted"
                job.lease_token = None
                job.lease_until = None
                await db.commit()
                continue
            token = uuid4()
            job.status = "running"
            job.lease_token = token
            job.lease_until = now + timedelta(minutes=3)
            job.attempts += 1
            job_id, task, payload, attempt = job.id, job.task, job.payload, job.attempts
            await db.commit()
        result, error = None, None
        try:
            import asyncio

            result = await asyncio.wait_for(handlers[task](ctx, **payload), timeout=35)
            if result.get("status", "").startswith(("skipped_", "missing_")):
                raise RuntimeError(result["status"])
        except Exception as exc:
            # Store only an error class; provider responses may include customer data or credentials.
            error = type(exc).__name__
        async with AsyncSessionLocal() as db:
            values = {"lease_until": None, "lease_token": None, "last_error": error}
            if error:
                values.update(
                    status="failed" if attempt >= 5 else "pending",
                    next_attempt_at=datetime.now(UTC)
                    + timedelta(seconds=min(3600, 30 * 2**attempt)),
                )
            else:
                values.update(
                    status="completed",
                    completed_at=datetime.now(UTC),
                    result={"status": result.get("status")},
                )
            await db.execute(
                update(CommerceJob)
                .where(CommerceJob.id == job_id, CommerceJob.lease_token == token)
                .values(**values)
            )
            await db.commit()
        count += 1
    return {"processed": count}
