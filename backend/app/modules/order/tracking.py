from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.security import decode_token


def tracking_token(order_id) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(order_id),
            "type": "order_tracking",
            "iat": now,
            "exp": now + timedelta(days=7),
        },
        get_settings().jwt_secret,
        algorithm="HS256",
    )


def read_tracking_token(token: str):
    from uuid import UUID

    try:
        data = decode_token(token)
        if data.get("type") != "order_tracking":
            raise ValueError()
        return UUID(data["sub"])
    except Exception as exc:
        raise HTTPException(
            403, "Liên kết tra cứu đã hết hạn hoặc không hợp lệ. Vui lòng yêu cầu gửi lại liên kết."
        ) from exc
