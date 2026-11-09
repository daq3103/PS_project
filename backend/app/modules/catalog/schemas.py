from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PetType(StrEnum):
    dog = "dog"
    cat = "cat"
    both = "both"


class LifeStage(StrEnum):
    baby = "baby"
    adult = "adult"
    senior = "senior"
    all = "all"


class ProductStatus(StrEnum):
    draft = "draft"
    active = "active"
    hidden = "hidden"


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    slug: str = Field(min_length=1, max_length=150)
    parent_id: UUID | None = None
    sort_order: int = 0
    is_active: bool = True
    show_in_nav: bool = False


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    slug: str | None = Field(default=None, min_length=1, max_length=150)
    parent_id: UUID | None = None
    sort_order: int | None = None
    is_active: bool | None = None
    show_in_nav: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    parent_id: UUID | None
    name: str
    slug: str
    sort_order: int
    is_active: bool
    show_in_nav: bool
    created_at: datetime


class VariantCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=150)
    options: dict = Field(default_factory=dict)
    price: int = Field(ge=0, description="VNĐ")
    compare_at_price: int | None = Field(default=None, ge=0)
    weight_grams: int = Field(gt=0)
    length_cm: int = Field(default=10, gt=0)
    width_cm: int = Field(default=10, gt=0)
    height_cm: int = Field(default=10, gt=0)
    low_stock_threshold: int = 5
    cached_available_qty: int = Field(default=0, ge=0)
    nearest_expiry_date: date | None = None
    is_active: bool = True


class VariantUpdate(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=150)
    options: dict | None = None
    price: int | None = Field(default=None, ge=0)
    compare_at_price: int | None = Field(default=None, ge=0)
    weight_grams: int | None = Field(default=None, gt=0)
    length_cm: int | None = Field(default=None, gt=0)
    width_cm: int | None = Field(default=None, gt=0)
    height_cm: int | None = Field(default=None, gt=0)
    low_stock_threshold: int | None = None
    cached_available_qty: int | None = Field(default=None, ge=0)
    nearest_expiry_date: date | None = None
    is_active: bool | None = None


class VariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    sku: str
    title: str
    options: dict
    price: int
    compare_at_price: int | None
    weight_grams: int
    length_cm: int
    width_cm: int
    height_cm: int
    low_stock_threshold: int
    cached_available_qty: int
    nearest_expiry_date: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductCreate(BaseModel):
    category_id: UUID
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)
    brand: str | None = None
    pet_type: PetType
    life_stage: LifeStage | None = None
    has_expiry: bool = False
    short_description: str | None = None
    description: str | None = None
    attributes: dict = Field(default_factory=dict)
    seo_title: str | None = None
    seo_description: str | None = None
    status: ProductStatus = ProductStatus.draft
    variants: list[VariantCreate] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    category_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=255)
    brand: str | None = None
    pet_type: PetType | None = None
    life_stage: LifeStage | None = None
    has_expiry: bool | None = None
    short_description: str | None = None
    description: str | None = None
    attributes: dict | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    status: ProductStatus | None = None


class ProductImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    variant_id: UUID | None
    r2_url: str
    alt_text: str | None
    sort_order: int
    created_at: datetime


class ProductImageUpdateIn(BaseModel):
    r2_url: str = Field(min_length=1)
    alt_text: str | None = None
    variant_id: UUID | None = None
    sort_order: int = 0


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category_id: UUID
    name: str
    slug: str
    brand: str | None
    pet_type: str
    life_stage: str | None
    has_expiry: bool
    short_description: str | None
    description: str | None
    attributes: dict
    seo_title: str | None
    seo_description: str | None
    rating_avg: Decimal
    rating_count: int
    total_sold: int
    status: str
    created_at: datetime
    updated_at: datetime
    variants: list[VariantOut] = Field(default_factory=list)
    images: list[ProductImageOut] = Field(default_factory=list)
