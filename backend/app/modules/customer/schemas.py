from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from app.core.phone import valid_contact_phone

_PHONE_RE = re.compile(r"^0\d{9,10}$")


def _validate_phone(value: str | None) -> str | None:
    if value is None:
        return value
    if not _PHONE_RE.fullmatch(value) or not valid_contact_phone(value):
        raise ValueError("Số điện thoại không hợp lệ")
    return value


class RegisterRequest(BaseModel):
    username: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_]{2,39}$")
    full_name: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=8, max_length=128)
    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.lower()


class LoginRequest(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=40)
    password: str = Field(min_length=1, max_length=128)
    totp_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    email: EmailStr | None = None
    phone: str | None = None

    @model_validator(mode="after")
    def require_contact(self) -> LoginRequest:
        if sum(bool(v) for v in (self.username, self.email, self.phone)) != 1:
            raise ValueError("Nhập tên tài khoản để đăng nhập")
        return self

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value: str | None) -> str | None:
        return _validate_phone(value)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetCodeVerify(PasswordResetRequest):
    code: str = Field(pattern=r"^[0-9]{6}$")


class PasswordResetCodeVerified(BaseModel):
    token: str


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    password: str = Field(min_length=8, max_length=128)


class PasswordResetAvailability(BaseModel):
    available: bool


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(min_length=20)
    link: bool = False
    totp_code: str | None = Field(default=None, pattern=r"^[0-9]{6}$")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None
    username: str | None = None
    google_linked: bool = False
    email_verified: bool = False
    phone: str | None
    full_name: str
    role: str
    totp_enabled: bool = False
    staff_permissions: list[str]
    created_at: datetime


class ProfileUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    phone: str | None = Field(default=None, min_length=10, max_length=11)

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value: str | None) -> str | None:
        return _validate_phone(value)


class AuthMeOut(BaseModel):
    user: UserOut | None
    admin_verified: bool = False
    csrf_token: str | None = None
    guest_token: str | None = None


class LoginChallengeOut(BaseModel):
    requires_totp: bool = True
