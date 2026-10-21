from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Float, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    __table_args__ = (
        CheckConstraint("kind IN ('page_view','LCP','INP','CLS','TTFB')"),
        CheckConstraint("value >= 0"),
        Index("ix_analytics_created_kind", "created_at", "kind"),
    )

    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    visitor_hash: Mapped[str] = mapped_column(String(64))
    session_hash: Mapped[str] = mapped_column(String(64))
    page: Mapped[str] = mapped_column(String(80))
    section: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(16))
    device: Mapped[str] = mapped_column(String(16))
    value: Mapped[float | None] = mapped_column(Float)
