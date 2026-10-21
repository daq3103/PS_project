import asyncio
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import require_owner
from app.core.rate_limit import client_ip, enforce_rate_limit
from app.core.redis import redis_cache
from app.modules.analytics import service, system
from app.modules.analytics.schemas import EventIn

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])
admin_router = APIRouter(
    prefix="/api/v1/admin/analytics",
    tags=["admin-analytics"],
    dependencies=[Depends(require_owner)],
)


@router.get("/config")
async def config(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"enabled": get_settings().analytics_enabled}


@router.post("/events", status_code=204)
async def collect(event: EventIn, request: Request, session: AsyncSession = Depends(get_db)):
    if not get_settings().analytics_enabled:
        return Response(status_code=204, headers={"Cache-Control": "no-store"})
    page = service.normalize_page(event.path)
    if page is None or request.headers.get("DNT") == "1" or request.headers.get("Sec-GPC") == "1":
        return Response(status_code=204, headers={"Cache-Control": "no-store"})
    await enforce_rate_limit(
        key=f"analytics:rate:{service.digest(client_ip(request))}", limit=180, window_seconds=60
    )
    # Heartbeats only touch Redis, never create database events every minute.
    if event.kind != "heartbeat":
        await service.save_event(session, event, *page)
    try:
        now = time.time()
        pipe = redis_cache.pipeline()
        for key in ("analytics:live:all", f"analytics:live:{page[1]}"):
            pipe.zremrangebyscore(key, "-inf", now - 300)
            pipe.zadd(key, {service.digest(str(event.session_id)): now})
            pipe.expire(key, 600)
        await asyncio.wait_for(pipe.execute(), timeout=0.1)
    except Exception:
        pass
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@admin_router.get("/traffic")
async def traffic(
    response: Response,
    days: int = Query(default=7, ge=1, le=90),
    section: Literal["all", "shop", "rescue", "account"] = "all",
    session: AsyncSession = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    if days not in {1, 7, 30, 90}:
        raise HTTPException(422, "Supported periods: 1, 7, 30, 90 days")
    data = await service.traffic_report(session, days, section)
    try:
        pipe = redis_cache.pipeline()
        key = f"analytics:live:{section}"
        pipe.zremrangebyscore(key, "-inf", time.time() - 300)
        pipe.zcard(key)
        _, online = await asyncio.wait_for(pipe.execute(), timeout=1)
        data["online"] = online
    except Exception:
        data["online"] = None
    data["enabled"] = get_settings().analytics_enabled
    return data


@admin_router.get("/system")
async def server(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return await system.snapshot()
