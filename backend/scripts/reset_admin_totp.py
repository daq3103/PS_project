"""Offline account recovery. Requires access to the server and explicit confirmation.

Never prints an existing secret or generates a bypass code. The owner must sign in
again with their password and enroll their own authenticator before admin writes.
"""
import argparse
import asyncio
import json
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal, engine
from app.models.user import RefreshToken, User


async def main(email: str, confirm: bool):
    try:
        async with AsyncSessionLocal() as session:
            user = await session.scalar(
                select(User).where(User.email == email).with_for_update()
            )
            if not user or not user.is_active or user.role != "owner":
                raise SystemExit("Recovery requires an active owner account.")
            if not user.password_hash:
                raise SystemExit("Account has no password; password sign-in must be available before recovery.")
            before = user.totp_enabled
            if confirm:
                user.totp_enabled = False
                user.totp_secret_encrypted = None
                user.auth_version += 1
                await session.execute(
                    update(RefreshToken)
                    .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
                    .values(revoked_at=datetime.now(UTC))
                )
                await session.commit()
            print(json.dumps({
                "email": email, "previously_enabled": before,
                "reset_completed": confirm,
                "next_step": "Sign in with password, then enroll a new authenticator in admin settings." if confirm else "Dry run only; pass --confirm to reset and revoke existing sessions.",
            }))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.email.strip(), args.confirm))
