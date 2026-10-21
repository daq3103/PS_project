"""Payment provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PaymentProvider(ABC):
    provider_code: str

    @abstractmethod
    async def create_payment(
        self,
        *,
        order_id: str,
        order_code: str,
        amount: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Return external_transaction_id, qr_code_url, raw_response."""

    @abstractmethod
    def verify_webhook(
        self,
        *,
        body: bytes,
        signature: str,
        timestamp: str,
    ) -> bool:
        ...

    @abstractmethod
    async def sync_status(
        self,
        *,
        external_transaction_id: str,
    ) -> dict[str, Any]:
        """Poll provider for payment status."""
