"""Pydantic schemas for the community rescue module."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

POST_TYPE = Literal["lost_pet", "found_pet", "adoption"]
PET_TYPE = Literal["dog", "cat", "other"]
MODERATION_STATUS = Literal["pending", "approved", "rejected", "hidden"]
LIFECYCLE_STATUS = Literal["open", "resolved", "closed", "expired"]
REPORT_STATUS = Literal["pending", "resolved", "dismissed"]
UPLOAD_STATUS = Literal["pending", "ready", "rejected"]
ADOPTION_STATUS = Literal["pending", "contacted", "approved", "completed", "rejected", "withdrawn"]


class AdoptionMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    age_months: int | None = Field(default=None, ge=0, le=480)
    size: Literal["small", "medium", "large", "unknown"] = "unknown"
    vaccinated: bool | None = None
    neutered: bool | None = None
    health: str | None = Field(default=None, max_length=1000)
    requirements: str | None = Field(default=None, max_length=1000)


COLOR = Literal["white", "black", "gray", "yellow", "brown", "orange", "cream"]
COAT = Literal["short", "medium", "long", "hairless", "unknown"]
SEX = Literal["male", "female", "unknown"]
SIZE = Literal["small", "medium", "large", "unknown"]
PATTERN = Literal["solid", "tabby", "spotted", "bicolor", "tricolor", "tortoiseshell", "unknown"]


class PetDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    colors: list[COLOR] = Field(default_factory=list, max_length=7)
    coat_length: COAT = "unknown"
    pattern: PATTERN = "unknown"
    sex: SEX = "unknown"
    size: SIZE = "unknown"
    age_months: int | None = Field(default=None, ge=0, le=480)
    weight_kg: float | None = Field(default=None, gt=0, le=500, allow_inf_nan=False)
    markings: str | None = Field(default=None, max_length=500)

    @field_validator("colors")
    @classmethod
    def unique_colors(cls, value):
        return list(dict.fromkeys(value))


class CommunityImageOut(BaseModel):
    upload_id: UUID
    object_key: str
    sort_order: int

    @model_validator(mode="before")
    @classmethod
    def from_image(cls, value):
        if hasattr(value, "upload"):
            return {
                "upload_id": value.upload_id,
                "object_key": value.upload.object_key,
                "sort_order": value.sort_order,
            }
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        return f"/api/proxy/api/v1/community/uploads/{self.object_key}"

    model_config = ConfigDict(from_attributes=True)


class CommunityPostPublicOut(BaseModel):
    id: UUID
    slug: str
    post_type: POST_TYPE
    title: str
    description: str | None
    pet_type: PET_TYPE
    breed: str | None
    color: str | None
    pet_details: PetDetails = Field(default_factory=PetDetails)
    location_detail: str | None
    province_name: str
    district_name: str | None
    ward_name: str | None
    last_seen_at: datetime | None
    found_at: datetime | None
    created_at: datetime
    images: list[CommunityImageOut]
    province_id: int
    district_id: int | None
    lifecycle_status: LIFECYCLE_STATUS
    adoption_meta: AdoptionMeta
    resolution_note: str | None
    expires_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def event_at(self) -> datetime | None:
        return self.last_seen_at if self.post_type == "lost_pet" else self.found_at

    model_config = ConfigDict(from_attributes=True)


class CommunityPostOwnerOut(CommunityPostPublicOut):
    moderation_status: MODERATION_STATUS
    lifecycle_status: LIFECYCLE_STATUS
    contact_phone: str
    contact_zalo: str | None
    contact_facebook: str | None
    expires_at: datetime
    version: int
    moderation_reason: str | None


class CommunityPostAdminOut(CommunityPostOwnerOut):
    author_user_id: UUID
    author_name: str = ""
    author_contact: str | None = None
    moderation_reason: str | None
    moderated_at: datetime | None


class CommunityFeedQs(BaseModel):
    post_type: POST_TYPE | None = None
    province_id: int | None = None
    pet_type: PET_TYPE | None = None
    district_id: int | None = None
    lifecycle_status: LIFECYCLE_STATUS = "open"
    cursor: str | None = None
    limit: int = Field(default=20, ge=1, le=50)
    q: str | None = Field(default=None, max_length=100)
    breed: str | None = Field(default=None, max_length=100)
    colors: str | None = Field(default=None, max_length=60)
    coat_length: COAT | None = None
    pattern: PATTERN | None = None
    sex: SEX | None = None
    size: SIZE | None = None
    date_from: date | None = Field(default=None, ge=date(1900, 1, 1), le=date(2100, 12, 31))
    date_to: date | None = Field(default=None, ge=date(1900, 1, 1), le=date(2100, 12, 31))

    @field_validator("colors")
    @classmethod
    def valid_colors(cls, value):
        from app.modules.community.pet_traits import COLORS

        if value and any(color not in COLORS for color in value.split(",")):
            raise ValueError("Màu lông không hợp lệ")
        return value

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc")
        return self


class CommunityPostCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    post_type: POST_TYPE
    title: str = Field(min_length=5, max_length=255)
    description: str | None = Field(default=None, max_length=3000)
    pet_type: PET_TYPE
    breed: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, max_length=100)
    pet_details: PetDetails = Field(default_factory=PetDetails)
    location_detail: str | None = Field(default=None, max_length=500)
    province_id: int
    province_name: str = Field(min_length=2, max_length=100)
    district_id: int | None = None
    district_name: str | None = Field(default=None, max_length=100)
    ward_code: str | None = Field(default=None, max_length=50)
    ward_name: str | None = Field(default=None, max_length=100)
    last_seen_at: AwareDatetime | None = None
    found_at: AwareDatetime | None = None
    contact_phone: str = Field(min_length=9, max_length=20)
    contact_zalo: str | None = Field(default=None, max_length=20)
    contact_facebook: str | None = Field(default=None, max_length=255)
    image_upload_ids: list[UUID] = Field(default_factory=list, max_length=5)
    adoption_meta: AdoptionMeta = Field(default_factory=AdoptionMeta)
    turnstile_token: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def validate_post(self):
        if self.post_type != "lost_pet" and self.last_seen_at:
            raise ValueError("Chỉ tin thất lạc dùng lần thấy cuối")
        if self.post_type != "found_pet" and self.found_at:
            raise ValueError("Chỉ tin nhặt được dùng thời điểm tìm thấy")
        if len(set(self.image_upload_ids)) != len(self.image_upload_ids):
            raise ValueError("Ảnh bị lặp")
        return self

    @field_validator("contact_facebook")
    @classmethod
    def safe_link(cls, value):
        if value:
            from urllib.parse import urlsplit

            url = urlsplit(value)
            if (
                url.scheme != "https"
                or url.hostname
                not in {
                    "facebook.com",
                    "www.facebook.com",
                    "m.facebook.com",
                    "fb.com",
                    "www.fb.com",
                }
                or url.username
            ):
                raise ValueError("Liên kết Facebook phải dùng https://facebook.com")
        return value

    @field_validator("image_upload_ids")
    @classmethod
    def _max_images(cls, value: list[UUID]) -> list[UUID]:
        if len(value) > 5:
            raise ValueError("Tối đa 5 ảnh")
        return value


class CommunityPostUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str | None = Field(default=None, min_length=5, max_length=255)
    description: str | None = Field(default=None, max_length=3000)
    pet_type: PET_TYPE | None = None
    breed: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, max_length=100)
    pet_details: PetDetails | None = None
    location_detail: str | None = Field(default=None, max_length=500)
    province_id: int | None = None
    province_name: str | None = Field(default=None, min_length=2, max_length=100)
    district_id: int | None = None
    district_name: str | None = Field(default=None, max_length=100)
    ward_code: str | None = Field(default=None, max_length=50)
    ward_name: str | None = Field(default=None, max_length=100)
    last_seen_at: AwareDatetime | None = None
    found_at: AwareDatetime | None = None
    contact_phone: str | None = Field(default=None, min_length=9, max_length=20)
    contact_zalo: str | None = Field(default=None, max_length=20)
    contact_facebook: str | None = Field(default=None, max_length=255)
    image_upload_ids: list[UUID] | None = Field(default=None, max_length=5)
    version: int = Field(ge=0)
    adoption_meta: AdoptionMeta | None = None

    @model_validator(mode="after")
    def required_values(self):
        for name in (
            "title",
            "pet_type",
            "province_id",
            "province_name",
            "contact_phone",
            "image_upload_ids",
            "adoption_meta",
            "pet_details",
        ):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} không được để trống")
        return self


class ContactRevealOut(BaseModel):
    contact_phone: str
    contact_zalo: str | None
    contact_facebook: str | None


class LifecycleActionIn(BaseModel):
    action: Literal["close", "resolve", "renew"]
    reason: str | None = Field(default=None, max_length=500)
    version: int | None = Field(default=None, ge=0)


class ModerationActionIn(BaseModel):
    action: Literal["approve", "reject", "hide"]
    reason: str | None = Field(default=None, max_length=500)
    version: int | None = Field(default=None, ge=0)


class ReportIn(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


class ReportOut(BaseModel):
    id: UUID
    reporter_user_id: UUID
    post_id: UUID
    reason: str
    status: REPORT_STATUS
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminListQs(BaseModel):
    q: str | None = Field(default=None, max_length=100)
    post_type: POST_TYPE | None = None
    moderation_status: MODERATION_STATUS | None = None
    lifecycle_status: LIFECYCLE_STATUS | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class AuditLogOut(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    action: str
    old_status: str | None
    new_status: str | None
    reason: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommunityFeedOut(BaseModel):
    items: list[CommunityPostPublicOut]
    next_cursor: str | None


class ReportHandleIn(BaseModel):
    action: Literal["resolved", "dismissed"]
    reason: str = Field(min_length=3, max_length=500)


class AdoptionCreateIn(BaseModel):
    consent: bool = False
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    applicant_name: str = Field(min_length=2, max_length=150)
    applicant_phone: str = Field(pattern=r"^\+?[0-9]{9,15}$")
    applicant_address: str = Field(min_length=5, max_length=1000)
    living_condition: str = Field(min_length=10, max_length=2000)


class AdoptionOut(BaseModel):
    applicant_name: str
    applicant_phone: str
    applicant_address: str
    living_condition: str
    id: UUID
    post_id: UUID
    status: ADOPTION_STATUS
    outcome_reason: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    anonymized_at: datetime | None
    post_title: str
    post_slug: str
    model_config = ConfigDict(from_attributes=True)


class AdoptionAdminOut(AdoptionOut):
    user_id: UUID
    admin_note: str | None
    handled_by: UUID | None


class AdoptionActionIn(BaseModel):
    action: Literal["contact", "approve", "reject", "complete"]
    reason: str | None = Field(default=None, max_length=500)
    admin_note: str | None = Field(default=None, max_length=1000)


class NotificationOut(BaseModel):
    id: UUID
    message: str
    href: str
    read_at: datetime | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
