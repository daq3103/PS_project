"""Run the suite against a newly created isolated PostgreSQL database.

Usage inside the backend runtime: python scripts/test_community.py
Never migrates or cleans the configured shop database.
"""

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
    test_name = "petshop_community_test_" + uuid.uuid4().hex[:12]
    connection = await asyncpg.connect(
        host=configured.host,
        port=configured.port or 5432,
        user=configured.username,
        password=configured.password,
        database=configured.database,
    )
    await connection.execute(f'CREATE DATABASE "{test_name}"')
    env = dict(os.environ)
    env.update(
        DATABASE_URL=configured.set(database=test_name).render_as_string(hide_password=False),
        COMMUNITY_TEST_DATABASE=test_name,
        COMMUNITY_UPLOAD_DIR=f"/tmp/{test_name}",
        APP_ENV="development",
        COMMUNITY_TURNSTILE_SECRET="",
        COMMUNITY_ENABLED="true",
    )
    try:
        migration = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"], env=env, check=False
        )
        if migration.returncode:
            return migration.returncode
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *sys.argv[1:]], env=env, check=False
        ).returncode
        if result:
            return result
        # Exercise rollback of only the additive revision, solely on this disposable database.
        subprocess.run([sys.executable, "-m", "alembic", "downgrade", "0002"], env=env, check=True)
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, check=True)
        return 0
    finally:
        # Only this randomly named database, created by this process, is removed.
        assert test_name.startswith("petshop_community_test_") and test_name != configured.database
        await connection.execute(f'DROP DATABASE "{test_name}" WITH (FORCE)')
        await connection.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
