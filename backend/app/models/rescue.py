"""Shelter records are independent of shop orders and sale inventory."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Record:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RescueAnimal(Record, Base):
    __tablename__ = "rescue_animals"
    __table_args__ = (
        CheckConstraint("species IN ('dog','cat')"),
        CheckConstraint("age_months IS NULL OR age_months >= 0"),
    )
    code: Mapped[str] = mapped_column(String(30), unique=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    species: Mapped[str] = mapped_column(String(10))
    sex: Mapped[str] = mapped_column(String(10), default="unknown")
    age_months: Mapped[int | None] = mapped_column(Integer)
    story: Mapped[str] = mapped_column(Text, default="")
    public_area: Mapped[str] = mapped_column(String(100), default="Hà Nội")
    care_summary: Mapped[str] = mapped_column(Text, default="")
    adoption_state: Mapped[str] = mapped_column(String(20), default="not_open")
    ownership_hold: Mapped[bool] = mapped_column(Boolean, default=False)
    publication: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    post_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("community_posts.id"), unique=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    profile: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))


class RescueLocation(Record, Base):
    __tablename__ = "rescue_locations"
    __table_args__ = (CheckConstraint("capacity > 0", name="ck_rescue_capacity"),)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))
    species: Mapped[str] = mapped_column(String(10), default="both")
    capacity: Mapped[int] = mapped_column(Integer)
    private_contact: Mapped[str] = mapped_column(Text, default="")
    available_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class RescueCase(Record, Base):
    __tablename__ = "rescue_cases"
    code: Mapped[str] = mapped_column(String(30), unique=True)
    summary: Mapped[str] = mapped_column(Text)
    coordinator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class RescueEpisode(Record, Base):
    __tablename__ = "rescue_episodes"
    __table_args__ = (
        Index(
            "uq_rescue_episode_open",
            "animal_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
    )
    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_animals.id")
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_cases.id")
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_locations.id")
    )
    assignee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(30))
    source_note: Mapped[str] = mapped_column(Text)


class RescueEvent(Record, Base):
    __tablename__ = "rescue_events"
    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_animals.id")
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(30))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    note: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    public: Mapped[bool] = mapped_column(Boolean, default=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_events.id")
    )


class RescueTask(Record, Base):
    __tablename__ = "rescue_tasks"
    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_animals.id")
    )
    episode_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_episodes.id")
    )
    assignee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="todo")
    occurrence_key: Mapped[str] = mapped_column(String(160), unique=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RescueReport(Record, Base):
    __tablename__ = "rescue_reports"
    code: Mapped[str] = mapped_column(String(30), unique=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    session_hash: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text)
    species: Mapped[str] = mapped_column(String(10))
    count_estimate: Mapped[int] = mapped_column(Integer)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    private_location: Mapped[str] = mapped_column(Text)
    private_contact: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="new")
    urgency: Mapped[str] = mapped_column(String(20), default="unassessed")
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_cases.id")
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)


class RescueReceipt(Record, Base):
    __tablename__ = "rescue_operation_receipts"
    scope: Mapped[str] = mapped_column(String(100))
    key: Mapped[str] = mapped_column(String(100))
    digest: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (Index("uq_rescue_operation_key", "scope", "key", unique=True),)


class RescueAudit(Record, Base):
    __tablename__ = "rescue_audit"
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)


class RescuePublication(Record, Base):
    __tablename__ = "rescue_publications"
    __table_args__ = (
        Index("uq_rescue_publication_version", "kind", "resource_id", "version", unique=True),
    )
    kind: Mapped[str] = mapped_column(String(20))
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer)
    approved_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    payload: Mapped[dict] = mapped_column(JSONB)


class RescueFund(Record, Base):
    __tablename__ = "rescue_funds"
    title: Mapped[str] = mapped_column(String(150))
    purpose: Mapped[str] = mapped_column(Text)
    surplus_policy: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    public_report: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))


class RescueLedger(Record, Base):
    __tablename__ = "rescue_ledger"
    __table_args__ = (CheckConstraint("amount > 0"),)
    fund_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rescue_funds.id"))
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(30))
    amount: Mapped[int] = mapped_column(BigInteger)
    reference: Mapped[str] = mapped_column(String(180), unique=True)
    donor_name: Mapped[str | None] = mapped_column(String(100))
    anonymous: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text)
    reverses_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_ledger.id")
    )


class RescueExpense(Record, Base):
    __tablename__ = "rescue_expenses"
    __table_args__ = (
        CheckConstraint("amount > 0"),
        CheckConstraint("approver_id IS NULL OR approver_id <> requester_id"),
    )
    fund_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rescue_funds.id"))
    requester_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    amount: Mapped[int] = mapped_column(BigInteger)
    purpose: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="requested")
    payment_reference: Mapped[str | None] = mapped_column(String(160), unique=True)


class RescueSupply(Record, Base):
    __tablename__ = "rescue_supply_receipts"
    __table_args__ = (
        CheckConstraint(
            "quantity > 0 AND accepted_quantity >= 0 AND accepted_quantity <= quantity"
        ),
    )
    name: Mapped[str] = mapped_column(String(150))
    quantity: Mapped[int] = mapped_column(Integer)
    accepted_quantity: Mapped[int] = mapped_column(Integer)
    unit: Mapped[str] = mapped_column(String(30))
    reference: Mapped[str] = mapped_column(String(160), unique=True)
    expiry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
