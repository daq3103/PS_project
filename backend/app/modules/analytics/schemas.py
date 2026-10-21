from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EventIn(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    event_id: UUID
    visitor_id: UUID
    session_id: UUID
    kind: Literal["page_view", "heartbeat", "LCP", "INP", "CLS", "TTFB"] = "page_view"
    path: str = Field(min_length=1, max_length=512)
    source: Literal["direct", "internal", "search", "social", "referral"] = "direct"
    device: Literal["mobile", "tablet", "desktop"] = "desktop"
    value: float | None = Field(default=None, ge=0, le=600000)

    @model_validator(mode="after")
    def validate_metric(self):
        if self.kind not in {"page_view", "heartbeat"} and self.value is None:
            raise ValueError("Metric value required")
        if self.kind == "CLS" and self.value is not None and self.value > 100:
            raise ValueError("Invalid CLS score")
        return self
