import asyncio
import time
from datetime import UTC, datetime
from pathlib import Path

import psutil
from sqlalchemy import text

from app.core.database import engine
from app.core.redis import redis_cache, redis_queue
from app.modules.analytics.metrics import request_report

STARTED = time.monotonic()


def resources() -> dict:
    process = psutil.Process()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    container_current = container_limit = None
    try:
        container_current = int(Path("/sys/fs/cgroup/memory.current").read_text())
        raw = Path("/sys/fs/cgroup/memory.max").read_text().strip()
        container_limit = int(raw) if raw != "max" else None
    except (OSError, ValueError):
        pass
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "cpu_scope": "host_visible_to_api",
        "cpu_cores": psutil.cpu_count(),
        "memory_used_bytes": memory.used,
        "memory_total_bytes": memory.total,
        "memory_percent": memory.percent,
        "container_memory_bytes": container_current,
        "container_limit_bytes": container_limit,
        "process_memory_bytes": process.memory_info().rss,
        "disk_used_bytes": disk.used,
        "disk_total_bytes": disk.total,
        "disk_percent": disk.percent,
        "process_uptime_seconds": round(time.monotonic() - STARTED),
    }


async def database_probe():
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return {}


async def redis_probe(client, queue=False):
    await client.ping()
    info = await client.info("memory")
    result = {"memory_bytes": info.get("used_memory"), "maxmemory_bytes": info.get("maxmemory")}
    if queue:
        result["queued_jobs"] = await client.zcard("arq:queue")
        # ARQ default health key; missing heartbeat is unknown, never reported as healthy.
        result["worker_heartbeat_present"] = bool(await client.exists("arq:queue:health-check"))
    return result


async def checked(callback):
    started = time.perf_counter()
    try:
        data = await asyncio.wait_for(callback(), timeout=2)
        return {
            "status": "up",
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            **data,
        }
    except Exception:
        return {"status": "down", "latency_ms": None}


async def snapshot() -> dict:
    system, db, cache, queue = await asyncio.gather(
        asyncio.to_thread(resources),
        checked(database_probe),
        checked(lambda: redis_probe(redis_cache)),
        checked(lambda: redis_probe(redis_queue, True)),
    )
    try:
        requests = await asyncio.wait_for(request_report(), timeout=2)
    except Exception:
        requests = {"available": False}
    return {
        "generated_at": datetime.now(UTC),
        "resources": system,
        "services": {"postgres": db, "redis_cache": cache, "redis_queue": queue},
        "api": requests,
    }
