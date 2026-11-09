from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AnimalIn(Input):
    name: str = Field(min_length=1, max_length=100)
    species: Literal["dog", "cat"]
    sex: Literal["male", "female", "unknown"] = "unknown"
    age_months: int | None = Field(None, ge=0, le=480)
    story: str = Field(default="", max_length=4000)
    care_summary: str = Field(default="", max_length=2000)
    public_area: str = Field(default="Hà Nội", min_length=2, max_length=100)
    post_id: UUID | None = None


class AnimalUpdate(AnimalIn):
    version: int = Field(ge=1)


class AnimalAction(Input):
    version: int = Field(ge=1)
    action: Literal["publish", "unpublish", "open", "pause", "hold", "release_hold"]
    reason: str = Field(min_length=5, max_length=1000)


class LocationIn(Input):
    name: str = Field(min_length=2, max_length=100)
    kind: Literal["shelter", "clinic", "foster", "transport"]
    species: Literal["dog", "cat", "both"] = "both"
    capacity: int = Field(ge=1, le=1000)
    private_contact: str = Field(default="", max_length=2000)
    available_from: AwareDatetime | None = None
    available_until: AwareDatetime | None = None

    @model_validator(mode="after")
    def ordered(self):
        if (
            self.available_from
            and self.available_until
            and self.available_until <= self.available_from
        ):
            raise ValueError("Thời gian kết thúc cần sau thời gian bắt đầu")
        return self


class IntakeIn(Input):
    animal_id: UUID
    location_id: UUID
    assignee_id: UUID
    case_id: UUID | None = None
    started_at: AwareDatetime
    source_note: str = Field(min_length=5, max_length=2000)


class TransferIn(Input):
    location_id: UUID
    assignee_id: UUID
    reason: str = Field(min_length=5, max_length=2000)
    handed_over: Literal[True]


class CloseIn(Input):
    outcome: Literal["returned_owner", "transferred", "deceased", "other"]
    reason: str = Field(min_length=5, max_length=2000)


class CareIn(Input):
    kind: Literal["observation", "care", "weight", "professional_record", "correction"]
    note: str = Field(min_length=3, max_length=4000)
    occurred_at: AwareDatetime
    supersedes_id: UUID | None = None


class TaskIn(Input):
    animal_id: UUID
    assignee_id: UUID
    title: str = Field(min_length=3, max_length=200)
    instructions: str = Field(min_length=3, max_length=4000)
    due_at: AwareDatetime


class TaskAction(Input):
    status: Literal["accepted", "in_progress", "completed", "skipped"]
    reason: str = Field(default="", max_length=1000)


class ReportIn(Input):
    description: str = Field(min_length=10, max_length=4000)
    species: Literal["dog", "cat", "unknown"]
    count_estimate: int = Field(default=1, ge=1, le=100)
    seen_at: AwareDatetime
    private_location: str = Field(min_length=5, max_length=1000)
    private_contact: str = Field(min_length=8, max_length=200)
    consent: Literal[True]


class ReportAction(Input):
    version: int = Field(ge=1)
    status: Literal[
        "verifying", "assigned", "in_progress", "completed", "referred", "duplicate", "closed"
    ]
    urgency: Literal["unassessed", "normal", "urgent"] = "unassessed"
    assignee_id: UUID | None = None
    case_id: UUID | None = None
    reason: str = Field(min_length=5, max_length=2000)


class CaseIn(Input):
    summary: str = Field(min_length=5, max_length=2000)
    coordinator_id: UUID


class FundIn(Input):
    title: str = Field(min_length=3, max_length=150)
    purpose: str = Field(min_length=10, max_length=4000)
    surplus_policy: str = Field(min_length=10, max_length=4000)


class LedgerIn(Input):
    kind: Literal["received", "settled", "fee", "refund"]
    amount: int = Field(gt=0, le=100000000000)
    reference: str = Field(min_length=6, max_length=160)
    donor_name: str | None = Field(default=None, max_length=100)
    anonymous: bool = True
    note: str = Field(min_length=10, max_length=2000)
    reverses_id: UUID | None = None


class ExpenseIn(Input):
    fund_id: UUID
    amount: int = Field(gt=0, le=100000000000)
    purpose: str = Field(min_length=10, max_length=2000)


class ExpenseAction(Input):
    action: Literal["approve", "reject", "pay"]
    reference: str = Field(default="", max_length=160)


class SupplyIn(Input):
    name: str = Field(min_length=2, max_length=150)
    quantity: int = Field(gt=0, le=1000000)
    accepted_quantity: int = Field(ge=0, le=1000000)
    unit: str = Field(min_length=1, max_length=30)
    reference: str = Field(min_length=6, max_length=160)
    expiry_at: AwareDatetime | None = None
    note: str = Field(min_length=5, max_length=2000)

    @model_validator(mode="after")
    def amounts(self):
        if self.accepted_quantity > self.quantity:
            raise ValueError("Lượng dùng được không vượt lượng thực nhận")
        return self
