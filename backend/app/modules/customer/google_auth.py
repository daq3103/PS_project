"""Google credentials are verified server-side; matching email never auto-links accounts."""
import secrets

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.id_token import verify_oauth2_token
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.cookies import set_auth_cookies, clear_guest_cookie
from app.core.database import get_db
from app.core.deps import get_current_user_optional
from app.core.encryption import decrypt_secret_str
from app.core.rate_limit import client_ip, enforce_rate_limit
from app.models.user import User
from app.modules.cart import service as cart_service
from app.modules.customer import auth_service
from app.modules.customer.schemas import GoogleLoginRequest, UserOut, LoginChallengeOut

router = APIRouter()

@router.get("/google/config")
async def google_config(response: Response):
    settings = get_settings()
    nonce = secrets.token_urlsafe(32)
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie("google_nonce", nonce, httponly=True, secure=settings.app_env != "development",
                        samesite="lax", max_age=600, path="/")
    return {"client_id": settings.google_client_id, "nonce": nonce}

def verify_credential(credential: str, nonce: str):
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(503, "Đăng nhập Google chưa được cấu hình.")
    try:
        claims = verify_oauth2_token(credential, GoogleRequest(), settings.google_client_id)
    except (ValueError, GoogleAuthError) as exc:
        raise HTTPException(401, "Không xác minh được tài khoản Google.") from exc
    if not nonce or not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise HTTPException(401, "Phiên Google đã hết hạn. Vui lòng tải lại trang.")
    if not claims.get("sub") or not claims.get("email") or claims.get("email_verified") is not True:
        raise HTTPException(401, "Google chưa xác minh email của tài khoản này.")
    return claims

@router.post("/google", response_model=UserOut | LoginChallengeOut)
async def google_login(body: GoogleLoginRequest, request: Request, response: Response,
                       session: AsyncSession = Depends(get_db),
                       current: User | None = Depends(get_current_user_optional)):
    await enforce_rate_limit(key=f"rl:google:{client_ip(request)}", limit=10, window_seconds=60)
    claims = await run_in_threadpool(verify_credential, body.id_token, request.cookies.get("google_nonce", ""))
    user = await session.scalar(select(User).where(User.google_id == claims["sub"]))
    email = claims["email"].lower()
    collision = await session.scalar(select(User).where(func.lower(User.email) == email).with_for_update())
    if body.link:
        if not current:
            raise HTTPException(401, "Đăng nhập tài khoản hiện có trước khi liên kết Google.")
        if (user and user.id != current.id) or (collision and collision.id != current.id):
            raise HTTPException(409, "Google hoặc email này đã thuộc tài khoản khác.")
        if current.google_id and current.google_id != claims["sub"]:
            raise HTTPException(409, "Tài khoản đã liên kết với Google khác.")
        user = current
        user.google_id = claims["sub"]
        if not user.email or user.email.lower() == email:
            user.email = email
            user.email_verified = True
    elif not user:
        if collision:
            if not collision.google_email_link_allowed or not email.endswith("@gmail.com") or collision.google_id:
                raise HTTPException(409, "Email đã thuộc tài khoản có sẵn. Hãy đăng nhập tài khoản đó và liên kết Google trong Hồ sơ.")
            user = collision
            user.google_id = claims["sub"]
            user.email_verified = True
            user.google_email_link_allowed = False
        else:
            user = User(google_id=claims["sub"], email=email, email_verified=True,
                        full_name=auth_service._sanitize_full_name(claims.get("name") or "Người dùng"), role="customer")
            session.add(user)
    if not user.is_active and user.id:
        raise HTTPException(403, "Tài khoản đã bị khóa.")
    verified = False
    if user.role == "owner" and user.totp_enabled:
        if not body.totp_code:
            return LoginChallengeOut()
        await enforce_rate_limit(key=f"rl:owner-mfa:{user.id}", limit=5, window_seconds=60)
        if not user.totp_secret_encrypted or not pyotp.TOTP(decrypt_secret_str(user.totp_secret_encrypted)).verify(body.totp_code, valid_window=1):
            raise HTTPException(401, "Mã xác thực không đúng hoặc đã hết hạn.")
        verified = True
    try:
        await session.flush()
        if not body.link:
            tokens = await auth_service.issue_session(session, user, mfa_verified=verified)
            guest = request.cookies.get("guest_token")
            if guest:
                await cart_service.merge_guest_cart_into_user(session, guest_token=guest, user_id=user.id)
                clear_guest_cookie(response)
            set_auth_cookies(response, **tokens)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Tài khoản đã tồn tại. Vui lòng thử đăng nhập lại.") from exc
    response.delete_cookie("google_nonce", path="/")
    response.headers["Cache-Control"] = "no-store"
    return UserOut.model_validate(user)
