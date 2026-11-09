"""Owner-only staff assignment for existing accounts."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import STAFF_PERMISSIONS, require_owner
from app.models.user import RefreshToken, StaffRoleChange, User

router = APIRouter(prefix="/api/v1/admin/staff", tags=["admin-staff"])

ASSIGNABLE_ROLES = frozenset({"customer", "warehouse_staff", "cskh_staff"})
ASSIGNABLE_PERMISSIONS = STAFF_PERMISSIONS


class StaffUserOut(BaseModel):
    id: UUID
    username: str | None
    full_name: str
    email: str | None
    phone: str | None
    role: str
    staff_permissions: list[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class StaffPermissionsIn(BaseModel):
    permissions: list[str] = Field(max_length=6)

    @field_validator("permissions")
    @classmethod
    def valid_permissions(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or not set(value) <= ASSIGNABLE_PERMISSIONS:
            raise ValueError("Quyền nhân viên không hợp lệ.")
        return sorted(value)


class StaffRoleChangeOut(BaseModel):
    target_user_id: UUID
    target_name: str
    actor_name: str
    old_role: str
    new_role: str
    old_permissions: list[str]
    new_permissions: list[str]
    created_at: datetime


@router.get("/users", response_model=list[StaffUserOut])
async def list_staff_candidates(
    q: str = Query(default="", max_length=100),
    _owner: User = Depends(require_owner),
    session: AsyncSession = Depends(get_db),
) -> list[User]:
    term = q.strip().lower()
    stmt = select(User)
    if term:
        if len(term) < 2:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Nhập ít nhất 2 ký tự để tìm tài khoản.")
        stmt = stmt.where(
            or_(
                func.lower(User.username).contains(term, autoescape=True),
                func.lower(User.full_name).contains(term, autoescape=True),
                func.lower(User.email).contains(term, autoescape=True),
                User.phone.contains(term, autoescape=True),
            )
        )
    else:
        stmt = stmt.where(User.role.in_(("warehouse_staff", "cskh_staff")))
    rows = await session.scalars(stmt.order_by(User.created_at.desc(), User.id).limit(25))
    return list(rows)


@router.patch("/users/{user_id}/permissions", response_model=StaffUserOut)
async def change_staff_permissions(
    user_id: UUID,
    body: StaffPermissionsIn,
    owner: User = Depends(require_owner),
    session: AsyncSession = Depends(get_db),
) -> User:
    if user_id == owner.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không thể tự thay đổi vai trò của mình.")
    target = await session.get(User, user_id, with_for_update=True)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài khoản.")
    if target.role not in ASSIGNABLE_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không thể thay đổi vai trò quản trị viên.")
    if not target.is_active and body.permissions:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Tài khoản đang bị khóa.")
    new_role = (
        "warehouse_staff" if "warehouse" in body.permissions
        else "cskh_staff" if body.permissions
        else "customer"
    )
    if target.role == new_role and sorted(target.staff_permissions or []) == body.permissions:
        return target

    old_role = target.role
    old_permissions = list(target.staff_permissions or [])
    target.role = new_role
    target.staff_permissions = body.permissions
    target.auth_version += 1
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == target.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    session.add(
        StaffRoleChange(
            actor_user_id=owner.id,
            target_user_id=target.id,
            old_role=old_role,
            new_role=new_role,
            old_permissions=old_permissions,
            new_permissions=body.permissions,
        )
    )
    await session.flush()
    return target


@router.get("/changes", response_model=list[StaffRoleChangeOut])
async def recent_staff_changes(
    _owner: User = Depends(require_owner),
    session: AsyncSession = Depends(get_db),
) -> list[StaffRoleChangeOut]:
    actor = User.__table__.alias("actor")
    target = User.__table__.alias("target")
    rows = await session.execute(
        select(
            StaffRoleChange.target_user_id,
            target.c.full_name.label("target_name"),
            actor.c.full_name.label("actor_name"),
            StaffRoleChange.old_role,
            StaffRoleChange.new_role,
            StaffRoleChange.old_permissions,
            StaffRoleChange.new_permissions,
            StaffRoleChange.created_at,
        )
        .join(actor, actor.c.id == StaffRoleChange.actor_user_id)
        .join(target, target.c.id == StaffRoleChange.target_user_id)
        .order_by(StaffRoleChange.created_at.desc(), StaffRoleChange.id.desc())
        .limit(20)
    )
    return [StaffRoleChangeOut.model_validate(row._mapping) for row in rows]
