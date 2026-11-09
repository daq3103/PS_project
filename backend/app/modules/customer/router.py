from __future__ import annotations

import logging
import pyotp

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import (
    clear_auth_cookies,
    clear_guest_cookie,
    set_auth_cookies,
    set_csrf_cookie,
    set_guest_cookie,
)
from app.core.database import get_db
from app.core.encryption import decrypt_secret_str
from app.core.deps import get_current_user_optional
from app.core.rate_limit import client_ip, enforce_rate_limit
from app.core.security import new_csrf_token, new_guest_token
from app.models.user import User
from app.modules.cart import service as cart_service
from app.modules.customer import auth_service, password_reset
from app.modules.customer.schemas import (
    AuthMeOut,
    LoginRequest,
    LoginChallengeOut,
    PasswordResetAvailability,
    PasswordResetConfirm,
    PasswordResetCodeVerify,
    PasswordResetCodeVerified,
    PasswordResetRequest,
    ProfileUpdateIn,
    RegisterRequest,
    UserOut,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
from app.modules.customer.google_auth import router as google_router
router.include_router(google_router)
from app.modules.customer.email_verification import router as email_router
router.include_router(email_router)
logger = logging.getLogger(__name__)


@router.get("/password-reset/config", response_model=PasswordResetAvailability)
async def password_reset_config(response: Response) -> PasswordResetAvailability:
    response.headers["Cache-Control"] = "no-store"
    return PasswordResetAvailability(available=password_reset.delivery_available())


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    body: PasswordResetRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    if not password_reset.delivery_available():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lấy lại mật khẩu qua email chưa sẵn sàng. Vui lòng thử lại sau.",
        )
    try:
        await enforce_rate_limit(
            key=f"rl:password-reset:ip:{client_ip(request)}", limit=5, window_seconds=3600
        )
        await enforce_rate_limit(
            key=f"rl:password-reset:email:{password_reset.account_rate_key(str(body.email))}",
            limit=3,
            window_seconds=3600,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Bạn đã yêu cầu quá nhiều lần. Vui lòng thử lại sau.",
            ) from exc
        raise

    code = await password_reset.create_reset_code(session, str(body.email))
    if code:
        try:
            await password_reset.send_reset_code_email(str(body.email), code)
        except HTTPException:
            await session.rollback()
            logger.warning("Password reset email delivery failed")
        else:
            await session.commit()
    return {"message": "Nếu email thuộc tài khoản PetHome, hãy kiểm tra hộp thư để tiếp tục."}


@router.post("/password-reset/verify-code", response_model=PasswordResetCodeVerified)
async def verify_password_reset_code(
    body: PasswordResetCodeVerify,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> PasswordResetCodeVerified:
    response.headers["Cache-Control"] = "no-store"
    await enforce_rate_limit(
        key=f"rl:password-code:ip:{client_ip(request)}", limit=30, window_seconds=600
    )
    await enforce_rate_limit(
        key=f"rl:password-code:email:{password_reset.account_rate_key(str(body.email))}",
        limit=10, window_seconds=600,
    )
    token = await password_reset.verify_reset_code(session, str(body.email), body.code)
    # Persist failed attempts before raising: dependency rollback must not reset the counter.
    await session.commit()
    if token is None:
        raise HTTPException(400, detail="Mã không đúng, đã hết hạn hoặc đã nhập sai quá nhiều lần. Vui lòng yêu cầu mã mới.")
    return PasswordResetCodeVerified(token=token)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(
    body: PasswordResetConfirm,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> None:
    await password_reset.consume_reset_token(session, body.token, body.password)
    await session.commit()
    clear_auth_cookies(response)
    response.headers["Cache-Control"] = "no-store"


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_db),
    guest_token: str | None = Cookie(default=None, alias="guest_token"),
) -> UserOut:
    user = await auth_service.register_user(
        session,
        full_name=body.full_name,
        password=body.password,
        username=body.username,
        email=None,
        phone=None,
    )
    tokens = await auth_service.issue_session(session, user)
    header_guest = request.headers.get("X-Guest-Token")
    gtoken = header_guest or guest_token
    if gtoken:
        await cart_service.merge_guest_cart_into_user(session, guest_token=gtoken, user_id=user.id)
        clear_guest_cookie(response)
    await session.commit()
    set_auth_cookies(response, **tokens)
    return UserOut.model_validate(user)


@router.post("/login", response_model=UserOut | LoginChallengeOut)
async def login(
    body: LoginRequest,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_db),
    guest_token: str | None = Cookie(default=None, alias="guest_token"),
) -> UserOut | LoginChallengeOut:
    response.headers["Cache-Control"] = "no-store"
    account_key = str(body.username or body.email or body.phone or "").lower()
    ip = client_ip(request)
    await enforce_rate_limit(
        key=f"rl:login:{ip}:{account_key}",
        limit=5,
        window_seconds=60,
    )
    user = await auth_service.authenticate_user(
        session,
        password=body.password,
        username=body.username,
        email=str(body.email) if body.email else None,
        phone=body.phone,
    )
    verified = False
    if user.role == "owner" and user.totp_enabled:
        if not body.totp_code:
            return LoginChallengeOut()
        await enforce_rate_limit(key=f"rl:owner-mfa:{user.id}", limit=5, window_seconds=60)
        if not user.totp_secret_encrypted or not pyotp.TOTP(decrypt_secret_str(user.totp_secret_encrypted)).verify(body.totp_code, valid_window=1):
            raise HTTPException(401, "Mã xác thực không đúng hoặc đã hết hạn.")
        verified = True
    tokens = await auth_service.issue_session(session, user, mfa_verified=verified)
    header_guest = request.headers.get("X-Guest-Token")
    gtoken = header_guest or guest_token
    if gtoken:
        await cart_service.merge_guest_cart_into_user(session, guest_token=gtoken, user_id=user.id)
        clear_guest_cookie(response)
    await session.commit()
    set_auth_cookies(response, **tokens)
    return UserOut.model_validate(user)


@router.post("/refresh", response_model=UserOut)
async def refresh(
    response: Response,
    session: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias="refresh_token"),
) -> UserOut:
    if not refresh_token:
        from fastapi import HTTPException

        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.")
    user, tokens = await auth_service.rotate_refresh(session, raw_refresh=refresh_token)
    await session.commit()
    set_auth_cookies(response, **tokens)
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias="refresh_token"),
) -> None:
    await auth_service.revoke_refresh(session, raw_refresh=refresh_token)
    await session.commit()
    clear_auth_cookies(response)


@router.get("/me", response_model=AuthMeOut)
async def me(
    response: Response,
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    guest_token: str | None = Cookie(default=None, alias="guest_token"),
    csrf_token: str | None = Cookie(default=None, alias="csrf_token"),
) -> AuthMeOut:
    response.headers["Cache-Control"] = "no-store"
    header_guest = request.headers.get("X-Guest-Token")
    gtoken = header_guest or guest_token
    if not user and not gtoken:
        gtoken = new_guest_token()
        set_guest_cookie(response, gtoken)
    if not csrf_token:
        csrf_token = new_csrf_token()
        set_csrf_cookie(response, csrf_token)
    return AuthMeOut(
        user=UserOut.model_validate(user) if user else None,
        admin_verified=getattr(request.state, "admin_verified", False),
        csrf_token=csrf_token,
        guest_token=gtoken,
    )


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: ProfileUpdateIn,
    user: User = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_db),
) -> UserOut:
    if not user:
        from fastapi import HTTPException

        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Vui lòng đăng nhập để tiếp tục.")
    updated = await auth_service.update_profile(
        session,
        user,
        full_name=body.full_name,
        phone=body.phone,
    )
    await session.commit()
    return UserOut.model_validate(updated)
