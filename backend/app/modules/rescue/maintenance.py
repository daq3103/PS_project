"""Small bounded maintenance jobs; no external providers, no global filesystem cleanup."""

from datetime import timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.rescue_workflow import RescueAsset
from app.modules.rescue import service as svc
from app.modules.rescue.workflow_service import maintenance


async def maintain_rescue(ctx):
    if get_settings().rescue_automation_paused:
        return {"paused": True}
    async with AsyncSessionLocal() as db:
        result = await maintenance(db)
        await db.commit()
        return result


async def cleanup_rescue_files(ctx):
    from starlette.concurrency import run_in_threadpool

    from app.modules.rescue.asset_router import asset_path

    async with AsyncSessionLocal() as db:
        rows = (
            await db.scalars(
                select(RescueAsset)
                .where(RescueAsset.deleted_at < svc.now() - timedelta(days=7))
                .limit(100)
            )
        ).all()
        for row in rows:
            await run_in_threadpool(asset_path(row.storage_key).unlink, missing_ok=True)
        return {"tombstones_checked": len(rows)}
