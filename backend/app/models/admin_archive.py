"""List removal keeps references, stock history and accounting records intact."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class AdminArchive(Base):
    __tablename__ = "admin_archives"
    resource_kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
