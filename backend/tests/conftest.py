"""Release shared async Redis pools before pytest closes each test's event loop."""

import pytest_asyncio

from app.core.redis import close_redis


@pytest_asyncio.fixture(autouse=True)
async def close_test_redis_pools():
    yield
    await close_redis()
