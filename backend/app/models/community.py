"""Community rescue models: lost/found pets and adoption posts."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CommunityUpload(Base):
    __tablename__ = "community_uploads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uploader_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    object_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, ready, rejected
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CommunityPost(Base):
    __tablename__ = "community_posts"
    __table_args__ = (Index("ix_community_pet_details", "pet_details", postgresql_using="gin"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    post_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # lost_pet, found_pet, adoption
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(300), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    pet_type: Mapped[str] = mapped_column(String(20), nullable=False)  # dog, cat, other
    breed: Mapped[str | None] = mapped_column(String(100))
    color: Mapped[str | None] = mapped_column(String(100))
    pet_details: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    adoption_meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    location_detail: Mapped[str | None] = mapped_column(String(500))
    province_id: Mapped[int] = mapped_column(Integer, nullable=False)
    province_name: Mapped[str] = mapped_column(String(100), nullable=False)
    district_id: Mapped[int | None] = mapped_column(Integer)
    district_name: Mapped[str | None] = mapped_column(String(100))
    ward_code: Mapped[str | None] = mapped_column(String(50))
    ward_name: Mapped[str | None] = mapped_column(String(100))

    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    found_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    contact_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    contact_zalo: Mapped[str | None] = mapped_column(String(20))
    contact_facebook: Mapped[str | None] = mapped_column(String(255))

    moderation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, approved, rejected, hidden
    lifecycle_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open"
    )  # open, resolved, closed, expired

    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(String(500))
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    moderated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    moderation_reason: Mapped[str | None] = mapped_column(String(500))

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    images: Mapped[list[CommunityPostImage]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="CommunityPostImage.sort_order",
    )
    reports: Mapped[list[CommunityReport]] = relationship(back_populates="post")
    audit_logs: Mapped[list[CommunityAuditLog]] = relationship(back_populates="post")


class CommunityPostImage(Base):
    __tablename__ = "community_post_images"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False
    )
    upload_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("community_uploads.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    post: Mapped[CommunityPost] = relationship(back_populates="images")
    upload: Mapped[CommunityUpload] = relationship(lazy="joined")


class CommunityReport(Base):
    __tablename__ = "community_reports"
    __table_args__ = (
        Index(
            "uq_community_pending_report",
            "post_id",
            "reporter_user_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, resolved, dismissed
    handled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    post: Mapped[CommunityPost] = relationship(back_populates="reports")


class CommunityAuditLog(Base):
    __tablename__ = "community_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    post_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("community_posts.id", ondelete="CASCADE")
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(50))
    new_status: Mapped[str | None] = mapped_column(String(50))
    reason: Mapped[str | None] = mapped_column(String(500))
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("adoption_requests.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    post: Mapped[CommunityPost | None] = relationship(back_populates="audit_logs")


class CommunityJobOutbox(Base):
    __tablename__ = "community_job_outbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, processing, done, failed
    attempt_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    unique_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(100))


class AdoptionRequest(Base):
    __tablename__ = "adoption_requests"
    __table_args__ = (
        Index(
            "uq_adoption_selected",
            "post_id",
            unique=True,
            postgresql_where=text("status IN ('approved','completed')"),
        ),
        Index(
            "uq_adoption_active_user",
            "post_id",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('pending','contacted','approved','completed')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    applicant_name: Mapped[str] = mapped_column(String(150), nullable=False)
    applicant_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    applicant_address: Mapped[str] = mapped_column(Text, nullable=False)
    living_condition: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    admin_note: Mapped[str | None] = mapped_column(String(1000))
    outcome_reason: Mapped[str | None] = mapped_column(String(500))
    handled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    post: Mapped[CommunityPost] = relationship(lazy="selectin")


class CommunityReceipt(Base):
    """A user-scoped idempotency receipt, written in the business transaction."""

    __tablename__ = "community_receipts"
    __table_args__ = (UniqueConstraint("user_id", "operation", "key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    operation: Mapped[str] = mapped_column(String(30))
    key: Mapped[str] = mapped_column(String(100))
    payload_hash: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommunityNotification(Base):
    __tablename__ = "community_notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    unique_key: Mapped[str] = mapped_column(String(64), unique=True)
    message: Mapped[str] = mapped_column(String(300))
    href: Mapped[str] = mapped_column(String(300))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
