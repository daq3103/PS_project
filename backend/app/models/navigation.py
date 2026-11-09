from sqlalchemy import Integer, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ShopNavigationSettings(Base):
    __tablename__ = "shop_navigation_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_shop_navigation_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    items: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
