from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CartItemAdd(BaseModel):
    variant_id: UUID
    qty: int = Field(default=1, gt=0, le=99)


class CartItemUpdate(BaseModel):
    qty: int = Field(gt=0, le=99)


class CartItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    variant_id: UUID
    qty: int
    sku: str | None = None
    title: str | None = None
    product_name: str | None = None
    product_slug: str | None = None
    unit_price: int | None = None
    cached_available_qty: int | None = None
    is_available: bool = True
    unavailable_label: str | None = None
    updated_at: datetime


class CartOut(BaseModel):
    id: UUID
    items: list[CartItemOut]
    item_count: int
    subtotal: int
