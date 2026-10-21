"""Separate Redis clients: cache (LRU) vs queue (AOF / noeviction)."""

from redis.asyncio import Redis

from app.core.config import get_settings

_settings = get_settings()

redis_cache: Redis = Redis.from_url(
    _settings.redis_cache_url_with_auth, decode_responses=True
)
redis_queue: Redis = Redis.from_url(
    _settings.redis_queue_url_with_auth, decode_responses=True
)


async def close_redis() -> None:
    await redis_cache.aclose()
    await redis_queue.aclose()
