from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.modules.rescue.schemas import Input


class Window(Input):
    starts_at: AwareDatetime
    ends_at: AwareDatetime

    @model_validator(mode="after")
    def ordered(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("Thời gian kết thúc phải sau bắt đầu")
        return self


class AppointmentIn(Window):
    animal_id: UUID
    application_id: UUID | None = None
    organizer_id: UUID
    participant_id: UUID
    kind: Literal["visit", "call", "handover", "trial"]
    location: str = Field(min_length=3, max_length=1000)


class AppointmentAction(Input):
    version: int = Field(ge=1)
    action: Literal["confirm", "cancel", "complete", "reschedule"]
    reason: str = Field(min_length=5, max_length=1000)
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None


class CheckIn(Input):
    action: Literal["verify", "agreement", "handover"]
    note: str = Field(min_length=10, max_length=4000)
    contact_method: Literal["phone", "in_person", "video_call"] = "phone"
    confirmed: Literal[True]


class ConsentIn(Input):
    purpose: Literal["adoption", "media", "updates"]
    allowed: bool


class PartnerIn(Input):
    kind: Literal["foster", "volunteer", "transport"]
    name: str = Field(min_length=2, max_length=150)
    contact: str = Field(min_length=8, max_length=200)
    area: str = Field(min_length=2, max_length=150)
    conditions: str = Field(min_length=10, max_length=4000)
    species: Literal["cat", "dog", "both"] = "both"
    capacity: int = Field(default=0, ge=0, le=100)
    available_from: AwareDatetime
    available_until: AwareDatetime
    consent: Literal[True]

    @model_validator(mode="after")
    def dates(self):
        if self.available_until <= self.available_from or (
            self.kind == "foster" and not self.capacity
        ):
            raise ValueError("Kiểm tra khoảng thời gian và sức chứa nhà chăm sóc tạm")
        return self


class DecisionIn(Input):
    version: int = Field(ge=1)
    action: Literal["approve", "reject", "pause", "withdraw"]
    reason: str = Field(min_length=5, max_length=2000)


class PartnerUpdateIn(PartnerIn):
    version: int = Field(ge=1)


class ShiftIn(Window):
    assignee_id: UUID
    backup_id: UUID
    instructions: str = Field(min_length=5, max_length=2000)


class ShiftAction(Input):
    version: int = Field(ge=1)
    action: Literal["accept", "handover", "cancel"]
    note: str = Field(min_length=5, max_length=2000)


class ScheduleIn(Input):
    animal_id: UUID
    title: str = Field(min_length=3, max_length=200)
    instructions: str = Field(min_length=5, max_length=4000)
    interval_days: int = Field(ge=1, le=365)
    next_at: AwareDatetime
    until_at: AwareDatetime


class SupplyMovementIn(Input):
    kind: Literal["use", "quarantine", "release", "dispose"]
    quantity: int = Field(gt=0, le=1000000)
    reason: str = Field(min_length=5, max_length=2000)
    reference: str = Field(min_length=8, max_length=160)


class NeedIn(Input):
    title: str = Field(min_length=3, max_length=150)
    unit: str = Field(min_length=1, max_length=30)
    quantity: int = Field(gt=0, le=1000000)
    instructions: str = Field(min_length=10, max_length=2000)


class PledgeIn(Input):
    need_id: UUID
    quantity: int = Field(gt=0, le=1000000)
    contact: str = Field(min_length=8, max_length=200)
    shop_order_id: UUID | None = None


class PledgeAction(Input):
    version: int = Field(ge=1)
    action: Literal["ship", "receive", "cancel"]
    reference: str = Field(min_length=6, max_length=160)
    quantity: int = Field(default=0, ge=0, le=1000000)
    accepted_quantity: int = Field(default=0, ge=0, le=1000000)
    expiry_at: AwareDatetime | None = None
    note: str = Field(min_length=5, max_length=2000)


class CampaignIn(Input):
    fund_id: UUID
    animal_id: UUID | None = None
    target: int = Field(gt=0, le=100000000000)
    opens_at: AwareDatetime
    closes_at: AwareDatetime
    surplus_action: Literal["hold", "refund"] = "hold"


class CampaignAction(Input):
    version: int = Field(ge=1)
    action: Literal["open", "pause", "close"]
    reason: str = Field(min_length=10, max_length=2000)


class DonationIn(Input):
    campaign_id: UUID
    amount: int = Field(ge=10000, le=100000000)
    anonymous: bool = True
    consent: Literal[True]


class DonationConfirm(Input):
    code: str = Field(min_length=8, max_length=30)
    amount: int = Field(gt=0, le=100000000000)
    reference: str = Field(min_length=6, max_length=160)
    merchant: str = Field(min_length=2, max_length=100)
    note: str = Field(min_length=10, max_length=2000)


class DonationReviewIn(DonationConfirm):
    decision: Literal["record", "keep_in_fund", "refund_planned"]


class RefundIn(Input):
    entry_id: UUID
    amount: int = Field(gt=0, le=100000000000)
    reason: str = Field(min_length=10, max_length=2000)


class RefundAction(Input):
    action: Literal["approve", "reject", "confirm_paid"]
    reference: str = Field(default="", max_length=160)
    confirmed: Literal[True]


class ProfileIn(Input):
    version: int = Field(ge=1)
    color: str = Field(default="", max_length=100)
    breed: str = Field(default="", max_length=100)
    size: Literal["unknown", "small", "medium", "large"] = "unknown"
    coat: Literal["unknown", "short", "medium", "long", "hairless"] = "unknown"
    video_url: str = Field(default="", max_length=500)
    behavior: str = Field(default="", max_length=2000)
    observed_at: AwareDatetime | None = None
    medical_summary: str = Field(default="", max_length=2000)


class MessageIn(Input):
    resource_kind: Literal["application", "report", "partner", "support"]
    resource_id: UUID
    body: str = Field(min_length=1, max_length=2000)


class PublicUpdateIn(Input):
    note: str = Field(min_length=5, max_length=2000)
    occurred_at: AwareDatetime
    rights_confirmed: Literal[True]


class VisitSlotIn(Window):
    animal_id: UUID
    organizer_id: UUID
    location: str = Field(min_length=3, max_length=1000)


class SlotBookingIn(Input):
    application_id: UUID


class ResponsibilityIn(Input):
    assignee_id: UUID
    reason: str = Field(min_length=5, max_length=2000)
    confirmed: Literal[True]
