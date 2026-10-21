"""Bounded Redis request counters shared by all Uvicorn workers (15 minute window)."""

import asyncio
import math
import time
from collections import defaultdict
from typing import Any

from app.core.config import get_settings
from app.core.redis import redis_cache

BUCKETS = (50, 100, 250, 500, 1000, 2500, 5000, 15000, 60000)
_retry_at = 0.0


class MetricsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not get_settings().analytics_enabled:
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        if not path.startswith("/api/v1/") or path.startswith(
            ("/api/v1/analytics/", "/api/v1/admin/analytics")
        ):
            return await self.app(scope, receive, send)
        started, status = time.perf_counter(), 500

        async def capture(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture)
        finally:
            route = getattr(scope.get("route"), "path", "/unmatched")
            duration = (time.perf_counter() - started) * 1000
            method = (
                scope["method"]
                if scope["method"] in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
                else "OTHER"
            )
            await record_request(f"{method} {route}", status, duration)


async def record_request(route: str, status: int, duration: float):
    global _retry_at
    if time.monotonic() < _retry_at:
        return
    duration = min(max(duration, 0), 600000)
    bucket = next((str(b) for b in BUCKETS if duration <= b), "inf")
    key = f"monitor:api:{int(time.time() // 60)}"

    async def write():
        pipe = redis_cache.pipeline()
        for field, value in {
            "n": 1,
            "e4": int(400 <= status < 500),
            "e5": int(status >= 500),
            "ms": round(duration),
            f"b:{bucket}": 1,
            f"r:{route}": 1,
            f"ms:{route}": round(duration),
            f"e5:{route}": int(status >= 500),
        }.items():
            pipe.hincrby(key, field, value)
        pipe.expire(key, 1200)
        await pipe.execute()

    try:
        await asyncio.wait_for(write(), timeout=0.05)
    except Exception:
        # Telemetry failure must never turn a successful shop request into an error.
        _retry_at = time.monotonic() + 30


async def request_report() -> dict:
    minute = int(time.time() // 60)
    pipe = redis_cache.pipeline()
    for index in range(15):
        pipe.hgetall(f"monitor:api:{minute - index}")
    rows = await pipe.execute()
    totals: dict[str, int] = defaultdict(int)
    timeline = []
    for index, row in enumerate(rows):
        for field, value in row.items():
            totals[field] += int(value)
        timeline.append(
            {
                "timestamp": (minute - index) * 60,
                "requests": int(row.get("n", 0)),
                "errors": int(row.get("e5", 0)),
            }
        )
    count = totals["n"]
    cumulative, p95 = 0, None
    for bucket in (*BUCKETS, "inf"):
        cumulative += totals[f"b:{bucket}"]
        if count and cumulative >= math.ceil(count * 0.95):
            p95 = bucket
            break
    routes: list[dict[str, Any]] = [
        {
            "route": field[2:],
            "requests": value,
            "average_ms": round(totals[f"ms:{field[2:]}"] / value, 1),
            "errors": totals[f"e5:{field[2:]}"],
        }
        for field, value in totals.items()
        if field.startswith("r:") and value
    ]
    return {
        "available": True,
        "window_minutes": 15,
        "requests": count,
        "client_errors": totals["e4"],
        "server_errors": totals["e5"],
        "average_ms": round(totals["ms"] / count, 1) if count else None,
        "p95_upper_ms": p95,
        "timeline": list(reversed(timeline)),
        "routes": sorted(routes, key=lambda r: r["requests"], reverse=True)[:15],
    }
