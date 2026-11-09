from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    username: Mapped[str | None] = mapped_column(String(40), unique=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    auth_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    totp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    totp_secret_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    google_email_link_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="customer")
    staff_permissions: Mapped[list[str]] = mapped_column(
        ARRAY(String(30)), nullable=False, default=list, server_default="{}"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    staff_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    addresses: Mapped[list[CustomerAddress]] = relationship(back_populates="user")
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(back_populates="user")
    password_reset_tokens: Mapped[list[PasswordResetToken]] = relationship(back_populates="user")

    @property
    def google_linked(self) -> bool:
        return bool(self.google_id)


class CustomerAddress(Base):
    __tablename__ = "customer_addresses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    recipient_name: Mapped[str] = mapped_column(String(150), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    province_id: Mapped[int] = mapped_column(nullable=False)
    province_name: Mapped[str] = mapped_column(String(100), nullable=False)
    district_id: Mapped[int] = mapped_column(nullable=False)
    district_name: Mapped[str] = mapped_column(String(100), nullable=False)
    ward_code: Mapped[str] = mapped_column(String(50), nullable=False)
    ward_name: Mapped[str] = mapped_column(String(100), nullable=False)
    street_address: Mapped[str] = mapped_column(String(255), nullable=False)
    full_address: Mapped[str | None] = mapped_column(String(255))
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="addresses")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    mfa_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    parent_token_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("refresh_tokens.id")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    code_hash: Mapped[str | None] = mapped_column(String(64))
    target_email: Mapped[str | None] = mapped_column(String(255))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="password_reset_tokens")


class StaffRoleChange(Base):
    __tablename__ = "staff_role_changes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    target_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    old_role: Mapped[str] = mapped_column(String(20), nullable=False)
    new_role: Mapped[str] = mapped_column(String(20), nullable=False)
    old_permissions: Mapped[list[str]] = mapped_column(ARRAY(String(30)), nullable=False)
    new_permissions: Mapped[list[str]] = mapped_column(ARRAY(String(30)), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
