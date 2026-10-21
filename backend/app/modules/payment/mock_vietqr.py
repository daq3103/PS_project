"""Mock VietQR payment provider (sandbox / local dev)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

from app.modules.payment.base import PaymentProvider

_WEBHOOK_TOLERANCE_SEC = 5 * 60
_AMOUNT_TOLERANCE = 1000


def amount_tolerance() -> int:
    return _AMOUNT_TOLERANCE


class MockVietQRProvider(PaymentProvider):
    provider_code = "mock_vietqr"

    def _webhook_secret(self) -> str:
        return os.environ.get("MOCK_VIETQR_WEBHOOK_SECRET", "mock_vietqr_webhook_secret_dev")

    async def create_payment(
        self,
        *,
        order_id: str,
        order_code: str,
        amount: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        ext_id = f"MQR-{order_code}-{secrets.token_hex(4).upper()}"
        qr_url = (
            f"https://mock.vietqr.io/qr?order={order_code}&amount={amount}&id={ext_id}"
        )
        return {
            "external_transaction_id": ext_id,
            "qr_code_url": qr_url,
            "raw_response": {
                "provider": self.provider_code,
                "idempotency_key": idempotency_key,
                "order_id": order_id,
                "amount": amount,
            },
        }

    def verify_webhook(
        self,
        *,
        body: bytes,
        signature: str,
        timestamp: str,
    ) -> bool:
        try:
            ts = int(timestamp)
        except ValueError:
            return False
        if abs(time.time() - ts) > _WEBHOOK_TOLERANCE_SEC:
            return False
        payload = timestamp.encode() + b"." + body
        expected = hmac.new(
            self._webhook_secret().encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def sync_status(
        self,
        *,
        external_transaction_id: str,
    ) -> dict[str, Any]:
        return {
            "external_transaction_id": external_transaction_id,
            "status": "pending",
            "actual_amount": 0,
        }

    @staticmethod
    def classify_amount(*, expected: int, actual: int) -> str:
        if actual < expected - _AMOUNT_TOLERANCE:
            return "underpaid"
        if actual > expected + _AMOUNT_TOLERANCE:
            return "overpaid"
        return "succeeded"

    @staticmethod
    def sign_webhook(body: bytes, timestamp: str | None = None) -> tuple[str, str]:
        """Helper for tests: build X-Timestamp + X-Signature."""
        ts = timestamp or str(int(time.time()))
        secret = os.environ.get("MOCK_VIETQR_WEBHOOK_SECRET", "mock_vietqr_webhook_secret_dev")
        payload = ts.encode() + b"." + body
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return ts, sig

    @staticmethod
    def parse_webhook_payload(body: bytes) -> dict[str, Any]:
        return json.loads(body.decode("utf-8"))
