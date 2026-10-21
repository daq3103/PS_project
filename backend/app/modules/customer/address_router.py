"""Customer address book CRUD under /api/v1/me/addresses."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import CustomerAddress, User

router = APIRouter(prefix="/api/v1/me/addresses", tags=["addresses"])


class AddressCreate(BaseModel):
    recipient_name: str = Field(min_length=1, max_length=150)
    recipient_phone: str = Field(min_length=8, max_length=20)
    province_id: int = Field(ge=0)
    province_name: str = Field(min_length=1, max_length=100)
    district_id: int = Field(ge=0)
    district_name: str = Field(min_length=1, max_length=100)
    ward_code: str = Field(min_length=1, max_length=50)
    ward_name: str = Field(min_length=1, max_length=100)
    street_address: str = Field(min_length=1, max_length=255)
    is_default: bool = False


class AddressUpdate(BaseModel):
    recipient_name: str | None = Field(default=None, min_length=1, max_length=150)
    recipient_phone: str | None = Field(default=None, min_length=8, max_length=20)
    province_id: int | None = Field(default=None, ge=0)
    province_name: str | None = Field(default=None, min_length=1, max_length=100)
    district_id: int | None = Field(default=None, ge=0)
    district_name: str | None = Field(default=None, min_length=1, max_length=100)
    ward_code: str | None = Field(default=None, min_length=1, max_length=50)
    ward_name: str | None = Field(default=None, min_length=1, max_length=100)
    street_address: str | None = Field(default=None, min_length=1, max_length=255)
    is_default: bool | None = None


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recipient_name: str
    recipient_phone: str
    province_id: int
    province_name: str
    district_id: int
    district_name: str
    ward_code: str
    ward_name: str
    street_address: str
    is_default: bool
    created_at: datetime


async def _clear_defaults(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(
        update(CustomerAddress)
        .where(CustomerAddress.user_id == user_id, CustomerAddress.is_default.is_(True))
        .values(is_default=False)
    )


@router.get("", response_model=list[AddressOut])
async def list_addresses(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[AddressOut]:
    rows = (
        await session.scalars(
            select(CustomerAddress)
            .where(CustomerAddress.user_id == user.id)
            .order_by(CustomerAddress.is_default.desc(), CustomerAddress.created_at.desc())
        )
    ).all()
    return [AddressOut.model_validate(r) for r in rows]


@router.post("", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
async def create_address(
    body: AddressCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AddressOut:
    count = await session.scalar(
        select(CustomerAddress.id).where(CustomerAddress.user_id == user.id).limit(1)
    )
    make_default = body.is_default or count is None
    if make_default:
        await _clear_defaults(session, user.id)
    payload = body.model_dump()
    payload["is_default"] = make_default
    addr = CustomerAddress(user_id=user.id, **payload)
    session.add(addr)
    await session.flush()
    return AddressOut.model_validate(addr)


@router.patch("/{address_id}", response_model=AddressOut)
async def update_address(
    address_id: UUID,
    body: AddressUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AddressOut:
    addr = await session.get(CustomerAddress, address_id)
    if not addr or addr.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Địa chỉ không tồn tại")
    data = body.model_dump(exclude_unset=True)
    if data.get("is_default") is True:
        await _clear_defaults(session, user.id)
    for k, v in data.items():
        setattr(addr, k, v)
    await session.flush()
    return AddressOut.model_validate(addr)


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(
    address_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    addr = await session.get(CustomerAddress, address_id)
    if not addr or addr.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Địa chỉ không tồn tại")
    was_default = addr.is_default
    await session.delete(addr)
    await session.flush()
    if was_default:
        next_addr = await session.scalar(
            select(CustomerAddress)
            .where(CustomerAddress.user_id == user.id)
            .order_by(CustomerAddress.created_at.desc())
            .limit(1)
        )
        if next_addr:
            next_addr.is_default = True
            await session.flush()
