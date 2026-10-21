from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    external_transaction_id: Mapped[str | None] = mapped_column(String(150))
    expected_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actual_amount: Mapped[int | None] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(25), nullable=False, default="pending")
    qr_code_url: Mapped[str | None] = mapped_column(Text)
    raw_response: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CarrierAccount(Base):
    __tablename__ = "carrier_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    carrier_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    shop_id: Mapped[str | None] = mapped_column(String(100))
    api_token_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    webhook_secret_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    pickup_address: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Fulfillment(Base):
    __tablename__ = "fulfillments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    carrier_code: Mapped[str] = mapped_column(String(30), nullable=False)
    tracking_code: Mapped[str | None] = mapped_column(String(100), unique=True)
    cod_amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cod_reconciled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cod_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_weight_grams: Mapped[int] = mapped_column(Integer, nullable=False)
    package_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    shipping_fee_charged_by_carrier: Mapped[int | None] = mapped_column(BigInteger)
    carrier_status: Mapped[str | None] = mapped_column(String(50))
    internal_status: Mapped[str] = mapped_column(String(30), nullable=False, default="ready_to_pick")
    label_print_url: Mapped[str | None] = mapped_column(Text)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    external_event_id: Mapped[str] = mapped_column(String(150), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    process_status: Mapped[str] = mapped_column(String(20), nullable=False, default="processed")
    error_message: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
