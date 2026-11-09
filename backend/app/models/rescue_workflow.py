"""Scheduling, participation and evidence for the single-station rescue workflow."""

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
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.rescue import Record


class RescueAppointment(Record, Base):
    __tablename__ = "rescue_appointments"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at"),
        Index("ix_rescue_appointment_time", "organizer_id", "starts_at"),
    )
    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_animals.id")
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("adoption_requests.id")
    )
    organizer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    participant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(String(20))
    location: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="proposed")
    version: Mapped[int] = mapped_column(Integer, default=1)
    change_reason: Mapped[str] = mapped_column(Text, default="")


class RescueApplicationCheck(Record, Base):
    __tablename__ = "rescue_application_checks"
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("adoption_requests.id"), unique=True
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contact_method: Mapped[str] = mapped_column(String(30), default="")
    verification_note: Mapped[str] = mapped_column(Text, default="")
    agreement: Mapped[str] = mapped_column(Text, default="")
    handover_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    handover_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    recipient_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class RescueConsent(Record, Base):
    __tablename__ = "rescue_consents"
    __table_args__ = (Index("uq_rescue_consent", "user_id", "purpose", "resource_id", unique=True),)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    purpose: Mapped[str] = mapped_column(String(30))
    policy_version: Mapped[str] = mapped_column(String(40))
    allowed: Mapped[bool] = mapped_column(Boolean)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RescuePartner(Record, Base):
    __tablename__ = "rescue_partners"
    __table_args__ = (
        CheckConstraint("capacity >= 0"),
        CheckConstraint("available_until > available_from"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(150))
    contact: Mapped[str] = mapped_column(String(200))
    area: Mapped[str] = mapped_column(String(150))
    conditions: Mapped[str] = mapped_column(Text)
    species: Mapped[str] = mapped_column(String(10))
    capacity: Mapped[int] = mapped_column(Integer)
    available_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    available_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    decision_note: Mapped[str] = mapped_column(Text, default="")
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_locations.id")
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    proposed_update: Mapped[dict] = mapped_column(JSONB, default=dict)


class RescueShift(Record, Base):
    __tablename__ = "rescue_shifts"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at"),
        Index("ix_rescue_shift_time", "assignee_id", "starts_at"),
    )
    assignee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    backup_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    instructions: Mapped[str] = mapped_column(Text)
    handover: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    version: Mapped[int] = mapped_column(Integer, default=1)


class RescueCareSchedule(Record, Base):
    __tablename__ = "rescue_care_schedules"
    __table_args__ = (CheckConstraint("interval_days > 0"),)
    episode_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_episodes.id")
    )
    title: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str] = mapped_column(Text)
    interval_days: Mapped[int] = mapped_column(Integer)
    next_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    until_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class RescueReminder(Record, Base):
    __tablename__ = "rescue_reminders"
    occurrence_key: Mapped[str] = mapped_column(String(200), unique=True)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RescueAsset(Record, Base):
    __tablename__ = "rescue_assets"
    resource_kind: Mapped[str] = mapped_column(String(20))
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    uploader_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    media_type: Mapped[str] = mapped_column(String(50))
    size: Mapped[int] = mapped_column(Integer)
    caption: Mapped[str] = mapped_column(String(200), default="")
    publication_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    public: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RescueSubscription(Record, Base):
    __tablename__ = "rescue_subscriptions"
    __table_args__ = (Index("uq_rescue_subscription", "animal_id", "user_id", unique=True),)
    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_animals.id")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    updates: Mapped[bool] = mapped_column(Boolean, default=False)


class RescueSupplyMovement(Record, Base):
    __tablename__ = "rescue_supply_movements"
    __table_args__ = (CheckConstraint("quantity > 0"),)
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_supply_receipts.id")
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    reference: Mapped[str] = mapped_column(String(160), unique=True)


class RescueSupplyNeed(Record, Base):
    __tablename__ = "rescue_supply_needs"
    title: Mapped[str] = mapped_column(String(150))
    unit: Mapped[str] = mapped_column(String(30))
    quantity: Mapped[int] = mapped_column(Integer)
    instructions: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")


class RescueSupplyPledge(Record, Base):
    __tablename__ = "rescue_supply_pledges"
    __table_args__ = (CheckConstraint("quantity > 0"),)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    need_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_supply_needs.id")
    )
    quantity: Mapped[int] = mapped_column(Integer)
    contact: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="pledged")
    tracking_reference: Mapped[str | None] = mapped_column(String(160), unique=True)
    receipt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_supply_receipts.id"), unique=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    shop_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), unique=True
    )


class RescueCampaign(Record, Base):
    __tablename__ = "rescue_campaigns"
    __table_args__ = (CheckConstraint("target > 0 AND closes_at > opens_at"),)
    fund_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_funds.id"), unique=True
    )
    animal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_animals.id")
    )
    target: Mapped[int] = mapped_column(BigInteger)
    opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    surplus_action: Mapped[str] = mapped_column(String(20), default="hold")
    version: Mapped[int] = mapped_column(Integer, default=1)


class RescueDonationIntent(Record, Base):
    __tablename__ = "rescue_donation_intents"
    __table_args__ = (CheckConstraint("amount > 0"),)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_campaigns.id")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    amount: Mapped[int] = mapped_column(BigInteger)
    anonymous: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    purpose_snapshot: Mapped[dict] = mapped_column(JSONB)
    ledger_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_ledger.id"), unique=True
    )


class RescueDonationEvent(Record, Base):
    __tablename__ = "rescue_donation_events"
    reference: Mapped[str] = mapped_column(String(160), unique=True)
    intent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_donation_intents.id")
    )
    amount: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(40))
    digest: Mapped[str] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(Text)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )


class RescueRefund(Record, Base):
    __tablename__ = "rescue_refunds"
    __table_args__ = (
        CheckConstraint("amount > 0"),
        CheckConstraint("approver_id IS NULL OR approver_id <> requester_id"),
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rescue_ledger.id"))
    requester_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    amount: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="requested")
    reference: Mapped[str | None] = mapped_column(String(160), unique=True)


class RescueMessage(Record, Base):
    __tablename__ = "rescue_messages"
    __table_args__ = (
        Index("ix_rescue_message_thread", "resource_kind", "resource_id", "created_at"),
    )
    resource_kind: Mapped[str] = mapped_column(String(20))
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    sender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)


class RescueVisitSlot(Record, Base):
    __tablename__ = "rescue_visit_slots"
    __table_args__ = (CheckConstraint("ends_at > starts_at"),)
    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_animals.id")
    )
    organizer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str] = mapped_column(Text)
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rescue_appointments.id"), unique=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
