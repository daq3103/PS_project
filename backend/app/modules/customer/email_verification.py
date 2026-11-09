"""Set a recovery email only after proving mailbox ownership."""
import secrets
import hmac
from datetime import UTC, datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.core.database import get_db
from app.core.deps import get_current_user_optional
from app.core.rate_limit import enforce_rate_limit
from app.core.security import hash_token
from app.models.user import User, PasswordResetToken
from app.modules.customer.schemas import PasswordResetRequest, PasswordResetCodeVerify
from app.modules.customer import password_reset as recovery

router = APIRouter()

@router.post("/me/email/request", status_code=202)
async def request_email(body: PasswordResetRequest, user: User | None = Depends(get_current_user_optional), session: AsyncSession = Depends(get_db)):
    if not user:
        raise HTTPException(401, "Vui lòng đăng nhập.")
    if not recovery.delivery_available():
        raise HTTPException(503, "Gửi email chưa sẵn sàng.")
    await enforce_rate_limit(key=f"rl:email-verify:{user.id}", limit=3, window_seconds=3600)
    email = str(body.email).lower()
    await session.get(User, user.id, with_for_update=True)
    if await session.scalar(select(User.id).where(func.lower(User.email) == email, User.id != user.id)):
        raise HTTPException(409, "Email đã thuộc tài khoản khác.")
    now = datetime.now(UTC)
    records = (await session.scalars(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.target_email.is_not(None), PasswordResetToken.used_at.is_(None)))).all()
    for record in records:
        record.used_at = now
    code = f"{secrets.randbelow(1_000_000):06d}"
    digest = hash_token(secrets.token_urlsafe(48))
    session.add(PasswordResetToken(user_id=user.id, target_email=email, token_hash=digest, code_hash=recovery._code_hash(digest, code), expires_at=now + recovery.CODE_TTL))
    await recovery._deliver_email(email, {"subject": "Xác minh email PetHome", "text": f"Mã xác minh email PetHome: {code}. Hiệu lực 10 phút. Không chia sẻ mã.", "html": f"<p>Mã xác minh email PetHome: <strong>{code}</strong></p><p>Hiệu lực 10 phút. Không chia sẻ mã.</p>"})
    await session.commit()
    return {"message": "Đã gửi mã xác minh email."}

@router.post("/me/email/verify", status_code=204)
async def verify_email(body: PasswordResetCodeVerify, user: User | None = Depends(get_current_user_optional), session: AsyncSession = Depends(get_db)):
    if not user:
        raise HTTPException(401, "Vui lòng đăng nhập.")
    await enforce_rate_limit(key=f"rl:email-verify-check:{user.id}", limit=10, window_seconds=600)
    await session.get(User, user.id, with_for_update=True)
    record = await session.scalar(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.target_email == str(body.email).lower(), PasswordResetToken.used_at.is_(None)).order_by(PasswordResetToken.created_at.desc()).limit(1).with_for_update())
    now = datetime.now(UTC)
    if not record or record.expires_at <= now or record.attempts >= 5:
        raise HTTPException(400, "Mã không đúng hoặc đã hết hạn.")
    record.attempts += 1
    if not hmac.compare_digest(record.code_hash, recovery._code_hash(record.token_hash, body.code)):
        await session.commit()
        raise HTTPException(400, "Mã không đúng hoặc đã hết hạn.")
    user.email = record.target_email
    user.email_verified = True
    record.used_at = now
    await session.execute(update(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)).values(used_at=now))
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Email đã thuộc tài khoản khác.") from exc
