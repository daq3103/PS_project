"""Mock GHN shipping provider with Redis-cached quotes."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.core.redis import redis_cache
from app.modules.shipping.base import ShippingProvider

_CACHE_TTL = 15 * 60


class MockGHNProvider(ShippingProvider):
    carrier_code = "mock_ghn"

    def _cache_key(self, shipping_address: dict[str, Any], total_weight_grams: int) -> str:
        payload = json.dumps(
            {"addr": shipping_address, "w": total_weight_grams},
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return f"ship:quote:{self.carrier_code}:{digest}"

    async def quote_fee(
        self,
        *,
        shipping_address: dict[str, Any],
        total_weight_grams: int,
    ) -> int:
        key = self._cache_key(shipping_address, total_weight_grams)
        cached = await redis_cache.get(key)
        if cached is not None:
            return int(cached)

        base = 25000
        per_kg = max(1, (total_weight_grams + 999) // 1000)
        fee = base + per_kg * 5000
        province = str(shipping_address.get("province_name") or "")
        if "Hà Nội" in province or "Ho Chi Minh" in province or "Hồ Chí Minh" in province:
            fee = max(20000, fee - 5000)

        await redis_cache.set(key, str(fee), ex=_CACHE_TTL)
        return fee

    async def create_shipment(
        self,
        *,
        order_id: str,
        shipping_address: dict[str, Any],
        total_weight_grams: int,
        cod_amount: int,
        attempt_no: int,
    ) -> dict[str, Any]:
        tracking = f"GHN{hashlib.sha256(f'{order_id}:{attempt_no}'.encode()).hexdigest()[:12].upper()}{attempt_no}"
        fee = await self.quote_fee(
            shipping_address=shipping_address,
            total_weight_grams=total_weight_grams,
        )
        return {
            "tracking_code": tracking,
            "label_print_url": f"https://mock.ghn.vn/labels/{tracking}.pdf",
            "carrier_status": "ready_to_pick",
            "shipping_fee_charged_by_carrier": fee,
            "cod_amount": cod_amount,
        }

    async def cancel_shipment(self, *, tracking_code: str) -> None:
        return None

    def map_carrier_status(self, carrier_status: str) -> str:
        mapping = {
            "ready_to_pick": "ready_to_pick",
            "picking": "picking",
            "delivering": "delivering",
            "delivered": "delivered",
            "delivery_failed": "delivery_failed",
            "returning": "returning",
            "returned": "returned",
            "cancelled": "cancelled",
        }
        return mapping.get(carrier_status, "delivering")
