from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

_PHONE_RE = re.compile(r"^0\d{9,10}$")


def _validate_phone(value: str | None) -> str | None:
    if value is None:
        return value
    if not _PHONE_RE.fullmatch(value):
        raise ValueError("Số điện thoại không hợp lệ")
    return value


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=8, max_length=128)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=10, max_length=11)

    @model_validator(mode="after")
    def require_contact(self) -> RegisterRequest:
        if not self.email and not self.phone:
            raise ValueError("Email hoặc SĐT là bắt buộc")
        return self

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value: str | None) -> str | None:
        return _validate_phone(value)


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    email: EmailStr | None = None
    phone: str | None = None

    @model_validator(mode="after")
    def require_contact(self) -> LoginRequest:
        if not self.email and not self.phone:
            raise ValueError("Email hoặc SĐT là bắt buộc")
        return self

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value: str | None) -> str | None:
        return _validate_phone(value)


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(min_length=20)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None
    phone: str | None
    full_name: str
    role: str
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
    csrf_token: str | None = None
    guest_token: str | None = None
