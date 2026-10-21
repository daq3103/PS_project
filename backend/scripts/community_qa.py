"""Serve an isolated, seeded rescue QA API on port 8000 inside a test container.

Writes only synthetic QA credentials to /tmp/community-qa.json. SIGTERM shuts down
the API and drops the randomly named database created by this process.
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
import uuid
from pathlib import Path

import asyncpg
import pyotp
from sqlalchemy.engine import make_url


async def main():
    Path("/tmp/community-qa.json").unlink(missing_ok=True)
    from app.core.config import get_settings

    configured = make_url(get_settings().database_url)
    test_name = "petshop_community_test_" + uuid.uuid4().hex[:12]
    admin = await asyncpg.connect(
        host=configured.host,
        port=configured.port or 5432,
        user=configured.username,
        password=configured.password,
        database=configured.database,
    )
    await admin.execute(f'CREATE DATABASE "{test_name}"')
    os.environ.update(
        DATABASE_URL=configured.set(database=test_name).render_as_string(hide_password=False),
        COMMUNITY_UPLOAD_DIR=f"/tmp/{test_name}",
        COMMUNITY_ENABLED="true",
        APP_ENV="development",
        COMMUNITY_TURNSTILE_SECRET="",
        TRUSTED_PROXY_CIDRS="",
    )
    get_settings.cache_clear()
    server = None
    try:
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
        from app.core.database import AsyncSessionLocal, engine
        from app.core.encryption import encrypt_secret
        from app.core.security import hash_password
        from app.models.user import User

        entries = {}
        async with AsyncSessionLocal() as session:
            for role in ("owner", "customer", "warehouse_staff"):
                password = uuid.uuid4().hex
                secret = pyotp.random_base32()
                row = User(
                    full_name=f"Community QA {role}",
                    role=role,
                    email=f"{role}-{uuid.uuid4().hex[:8]}@example.com",
                    password_hash=hash_password(password),
                    totp_enabled=role != "customer",
                    totp_secret_encrypted=encrypt_secret(secret) if role != "customer" else None,
                )
                session.add(row)
                await session.flush()
                entries[role] = {
                    "id": str(row.id),
                    "email": row.email,
                    "password": password,
                    "totp": secret,
                }
            await session.commit()
        await engine.dispose()
        Path("/tmp/community-qa.json").write_text(json.dumps(entries), encoding="utf-8")
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--no-proxy-headers",
            ]
        )
        stopping = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stopping.set)
        while server.poll() is None and not stopping.is_set():
            try:
                await asyncio.wait_for(stopping.wait(), timeout=1)
            except TimeoutError:
                pass
    finally:
        if server and server.poll() is None:
            server.terminate()
            await asyncio.to_thread(server.wait, timeout=15)
        assert test_name.startswith("petshop_community_test_") and test_name != configured.database
        await admin.execute(f'DROP DATABASE "{test_name}" WITH (FORCE)')
        await admin.close()


if __name__ == "__main__":
    asyncio.run(main())
