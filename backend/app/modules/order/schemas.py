"""Order / checkout API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.phone import valid_contact_phone

from app.models.commerce import Order, OrderItem


class CheckoutItemIn(BaseModel):
    variant_id: UUID
    qty: int = Field(gt=0, le=99)


class CheckoutRequest(BaseModel):
    quote_id: UUID | None = None
    idempotency_key: str = Field(min_length=8, max_length=100)
    customer_name: str = Field(min_length=1, max_length=150)
    customer_phone: str = Field(min_length=8, max_length=20)
    customer_email: EmailStr | None = Field(default=None, max_length=255)
    shipping_address: dict[str, Any]
    payment_method: Literal["cod", "vietqr"]
    customer_note: str | None = Field(default=None, max_length=2000)
    promo_code: str | None = Field(default=None, max_length=50)
    items: list[CheckoutItemIn] | None = Field(default=None, max_length=100)

    @field_validator("customer_phone")
    @classmethod
    def check_customer_phone(cls, value: str) -> str:
        value = value.strip()
        if not valid_contact_phone(value):
            raise ValueError("Số điện thoại không hợp lệ. Vui lòng nhập số liên lạc thật.")
        return value


class OrderItemOut(BaseModel):
    id: UUID
    variant_id: UUID
    product_name_snapshot: str
    variant_title_snapshot: str
    sku_snapshot: str
    qty: int
    unit_price: int
    line_total: int
    discount_amount: int = 0

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: UUID
    order_code: str
    status: str
    payment_method: str
    payment_status: str
    subtotal_amount: int
    discount_amount: int
    shipping_fee: int
    shipping_discount: int
    total_amount: int
    customer_name: str
    customer_phone: str
    customer_email: str | None
    shipping_address: dict[str, Any]
    reservation_expires_at: datetime | None
    customer_note: str | None
    coupon_code_snapshot: str | None
    created_at: datetime
    items: list[OrderItemOut] = []
    tracking_token: str | None = None

    @classmethod
    def from_order(cls, order: Order, items: list[OrderItem] | None = None) -> OrderOut:
        item_out = (
            [OrderItemOut.model_validate(i) for i in items]
            if items is not None
            else []
        )
        return cls(
            id=order.id,
            order_code=order.order_code,
            status=order.status,
            payment_method=order.payment_method,
            payment_status=order.payment_status,
            subtotal_amount=order.subtotal_amount,
            discount_amount=order.discount_amount,
            shipping_fee=order.shipping_fee,
            shipping_discount=order.shipping_discount,
            total_amount=order.total_amount,
            customer_name=order.customer_name,
            customer_phone=order.customer_phone,
            customer_email=order.customer_email,
            shipping_address=order.shipping_address,
            reservation_expires_at=order.reservation_expires_at,
            customer_note=order.customer_note,
            coupon_code_snapshot=order.coupon_code_snapshot,
            created_at=order.created_at,
            items=item_out,
        )


class OrderTrackOut(BaseModel):
    order_code: str
    status: str
    payment_status: str
    total_amount: int
    customer_name: str
    customer_phone_masked: str
    shipping_address: dict[str, Any]
    created_at: datetime
    items: list[OrderItemOut] = []


class CancelOrderRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


def mask_phone(phone: str) -> str:
    digits = phone.strip()
    if len(digits) <= 4:
        return "***"
    if len(digits) <= 7:
        return digits[:2] + "***" + digits[-1:]
    mid_start = len(digits) // 2 - 1
    return digits[: mid_start] + "***" + digits[mid_start + 3 :]


def mask_address(addr: dict[str, Any]) -> dict[str, Any]:
    out = dict(addr)
    street = str(out.pop("full_address", None) or out.pop("street_address", None) or out.pop("street", None) or "")
    if len(street) > 6:
        out["street_address"] = street[:3] + "…" + street[-2:]
    elif street:
        out["street_address"] = "…"
    for key in ("recipient_phone", "phone"):
        if key in out and out[key]:
            out[key] = mask_phone(str(out[key]))
    return out
