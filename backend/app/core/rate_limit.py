"""Simple Redis fixed-window rate limiter."""

from __future__ import annotations

import ipaddress

from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.core.redis import redis_cache


async def enforce_rate_limit(*, key: str, limit: int, window_seconds: int) -> None:
    pipe = redis_cache.pipeline()
    pipe.incr(key)
    pipe.expire(key, window_seconds, nx=True)
    count, _ = await pipe.execute()
    if int(count) > limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({limit}/{window_seconds}s)",
        )


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    try:
        networks = [
            ipaddress.ip_network(c.strip())
            for c in get_settings().trusted_proxy_cidrs.split(",")
            if c.strip()
        ]
        if not any(ipaddress.ip_address(peer) in n for n in networks):
            return peer
        # Walk right-to-left; the first untrusted hop is the client. Nginx replaces XFF.
        hops = request.headers.get("X-Forwarded-For", "").split(",")
        for hop in reversed(hops):
            address = ipaddress.ip_address(hop.strip())
            if not any(address in n for n in networks):
                return str(address)
    except ValueError:
        return peer
    return peer
