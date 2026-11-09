"""payOS hosted checkout. Credentials never leave the backend except to payOS."""

import hashlib
import hmac
import json
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings

BASE_URL = "https://api-merchant.payos.vn"


def online_provider_code():
    return "mock_vietqr" if get_settings().payment_provider == "mock" else "payos"


def online_available():
    s = get_settings()
    if s.payment_provider == "mock":
        return s.app_env == "development"
    return s.payment_provider == "payos" and all(
        (
            s.payos_client_id,
            s.payos_api_key,
            s.payos_checksum_key,
            s.app_public_url.startswith("https://"),
        )
    )


def signature(data: dict, key: str) -> str:
    def value(item):
        if item is None or item in ("null", "undefined", "NULL"):
            return ""
        if isinstance(item, (dict, list)):
            return json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return str(item)

    canonical = "&".join(f"{name}={value(data[name])}" for name in sorted(data))
    return hmac.new(key.encode(), canonical.encode(), hashlib.sha256).hexdigest()


def verify_data(data: dict, supplied: str) -> bool:
    key = get_settings().payos_checksum_key
    return bool(
        key and isinstance(supplied, str) and hmac.compare_digest(signature(data, key), supplied)
    )


class PayOSProvider:
    async def request(self, method, path, payload=None):
        s = get_settings()
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.request(
                method,
                BASE_URL + path,
                headers={"x-client-id": s.payos_client_id, "x-api-key": s.payos_api_key},
                json=payload,
            )
        response.raise_for_status()
        body = response.json()
        if body.get("code") != "00" or not isinstance(body.get("data"), dict):
            raise RuntimeError("payOS request failed")
        if not verify_data(body["data"], body.get("signature", "")):
            raise RuntimeError("payOS response signature mismatch")
        return body["data"]

    async def create_or_get(self, *, order_code, amount, expires_at):
        s = get_settings()
        reference = int(order_code, 36)
        payload = {
            "orderCode": reference,
            "amount": amount,
            "description": order_code[-9:],
            "returnUrl": s.app_public_url.rstrip("/") + "/track-order",
            "cancelUrl": s.app_public_url.rstrip("/") + "/track-order",
        }
        payload["signature"] = signature(
            {
                k: payload[k]
                for k in ("amount", "cancelUrl", "description", "orderCode", "returnUrl")
            },
            s.payos_checksum_key,
        )
        if expires_at:
            payload["expiredAt"] = int(expires_at.timestamp())
        try:
            result = await self.request("POST", "/v2/payment-requests", payload)
        except (httpx.HTTPError, RuntimeError) as exc:
            # Every retry retains the same provider orderCode. Recover an existing link
            # after timeout or duplicate creation; never mint a new charge reference.
            result = await self.request("GET", f"/v2/payment-requests/{reference}")
            link_id = result.get("id", "")
            if (
                not isinstance(link_id, str)
                or len(link_id) != 32
                or not all(c in "0123456789abcdef" for c in link_id.lower())
            ):
                raise RuntimeError("Invalid payOS link reference") from exc
            result["checkoutUrl"] = f"https://pay.payos.vn/web/{link_id}"
            result["paymentLinkId"] = link_id
        if result.get("amount") != amount or result.get("orderCode") != reference:
            raise RuntimeError("payOS amount or reference mismatch")
        checkout_url = result.get("checkoutUrl", "")
        parsed = urlparse(checkout_url)
        if parsed.scheme != "https" or parsed.hostname != "pay.payos.vn":
            raise RuntimeError("Unexpected payOS checkout URL")
        return result
