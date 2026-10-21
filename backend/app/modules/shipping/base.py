"""Shipping provider abstraction (design v1.3)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ShippingProvider(ABC):
    carrier_code: str

    @abstractmethod
    async def quote_fee(
        self,
        *,
        shipping_address: dict[str, Any],
        total_weight_grams: int,
    ) -> int:
        """Return shipping fee in VND."""

    @abstractmethod
    async def create_shipment(
        self,
        *,
        order_id: str,
        shipping_address: dict[str, Any],
        total_weight_grams: int,
        cod_amount: int,
        attempt_no: int,
    ) -> dict[str, Any]:
        """Return dict with tracking_code, label_print_url, carrier_status, fee, etc."""

    @abstractmethod
    async def cancel_shipment(self, *, tracking_code: str) -> None:
        ...

    @abstractmethod
    def map_carrier_status(self, carrier_status: str) -> str:
        """Map carrier status → fulfillments.internal_status."""
