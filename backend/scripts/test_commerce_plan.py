"""Create/migrate/test/drop only a new random database. No shop migrations or data changes."""

import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
from sqlalchemy.engine import make_url

from app.core.config import get_settings


async def main():
    configured = make_url(get_settings().database_url)
    name = "pethome_plan_test_" + uuid.uuid4().hex[:12]
    connection = await asyncpg.connect(
        host=configured.host,
        port=configured.port or 5432,
        user=configured.username,
        password=configured.password,
        database=configured.database,
    )
    await connection.execute(f'CREATE DATABASE "{name}"')
    marker = Path("/tmp/pethome-active-test-database")
    marker.write_text(name, encoding="utf-8")
    env = dict(
        os.environ,
        DATABASE_URL=configured.set(database=name).render_as_string(hide_password=False),
        COMMUNITY_TEST_DATABASE=name,
        COMMUNITY_UPLOAD_DIR=f"/tmp/{name}",
        APP_ENV="development",
        COMMUNITY_ENABLED="true",
        COMMUNITY_TURNSTILE_SECRET="",
        DB_POOL_SIZE="2",
        DB_MAX_OVERFLOW="1",
        PAYMENT_PROVIDER="mock",
        PAYOS_CLIENT_ID="",
        PAYOS_API_KEY="",
        PAYOS_CHECKSUM_KEY="",
    )
    for env_key, configured_url in (("REDIS_CACHE_URL", get_settings().redis_cache_url),
                                    ("REDIS_QUEUE_URL", get_settings().redis_queue_url)):
        parts = urlsplit(configured_url)
        env[env_key] = urlunsplit(parts._replace(path="/15"))
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"], env=env, check=False
        )
        if result.returncode:
            return result.returncode
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "--tb=short", *sys.argv[1:]],
            env=env,
            check=False,
        )
        return result.returncode
    finally:
        assert name.startswith("pethome_plan_test_") and name != configured.database
        await connection.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        marker.unlink(missing_ok=True)
        await connection.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
