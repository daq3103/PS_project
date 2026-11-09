"""Run regression tests in a newly created disposable database, never the app DB."""
import asyncio
import os
import subprocess
import sys
import uuid
import asyncpg
from sqlalchemy.engine import make_url
from app.core.config import get_settings


async def main():
    configured = make_url(get_settings().database_url)
    name = "pethome_v2_test_" + uuid.uuid4().hex[:12]
    connection = await asyncpg.connect(host=configured.host, port=configured.port or 5432,
        user=configured.username, password=configured.password, database=configured.database)
    await connection.execute(f'CREATE DATABASE "{name}"')
    env = dict(os.environ, DATABASE_URL=configured.set(database=name).render_as_string(hide_password=False),
        PETHOME_V2_TEST_DATABASE=name, APP_ENV="development", COMMUNITY_ENABLED="true", COMMUNITY_TURNSTILE_SECRET="")
    try:
        result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env)
        if result.returncode:
            return result.returncode
        return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "asyncio_default_fixture_loop_scope=function", *sys.argv[1:]], env=env).returncode
    finally:
        assert name.startswith("pethome_v2_test_") and name != configured.database
        await connection.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await connection.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
