"""Platform operators can run the app but cannot delegate access."""
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from app.core.deps import (
    STAFF_PERMISSIONS, get_current_user, has_staff_permission,
    require_owner, require_platform_manager,
)


def manager():
    return SimpleNamespace(role="warehouse_staff", staff_permissions=["platform_manage"])


@pytest.mark.asyncio
async def test_platform_manager_is_not_owner():
    user = manager()
    assert await require_platform_manager(user=user) is user
    assert all(has_staff_permission(user, permission) for permission in STAFF_PERMISSIONS)
    with pytest.raises(HTTPException) as exc:
        await require_owner(user=user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_regular_staff_cannot_gain_platform_rights():
    for role, permissions in [("warehouse_staff", ["warehouse"]), ("customer", ["platform_manage"])]:
        user = SimpleNamespace(role=role, staff_permissions=permissions)
        assert not has_staff_permission(user, "platform_manage")
        with pytest.raises(HTTPException) as exc:
            await require_platform_manager(user=user)
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_platform_manager_cannot_read_or_change_staff_via_api():
    from app.core.database import get_db
    from app.main import app

    async def no_database():
        yield None  # Every request must fail its authorization guard before DB use.

    app.dependency_overrides[get_current_user] = lambda: manager()
    app.dependency_overrides[get_db] = no_database
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for path in ["/api/v1/admin/staff/users", "/api/v1/admin/staff/changes"]:
                assert (await client.get(path)).status_code == 403
            response = await client.patch(
                "/api/v1/admin/staff/users/00000000-0000-0000-0000-000000000001/permissions",
                json={"permissions": ["platform_manage"]},
            )
            assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_assignable_permission_is_explicit_and_validated():
    from app.modules.admin.staff_router import StaffPermissionsIn
    from pydantic import ValidationError

    assert StaffPermissionsIn(permissions=sorted(STAFF_PERMISSIONS)).permissions == sorted(STAFF_PERMISSIONS)
    for permissions in [["owner"], ["platform_manage", "platform_manage"], ["manage_staff"]]:
        with pytest.raises(ValidationError):
            StaffPermissionsIn(permissions=permissions)
