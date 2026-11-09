"""Authorization helpers for the community rescue module."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, has_staff_permission
from app.models.community import CommunityPost
from app.models.user import User


def is_rescue_staff(user: User) -> bool:
    return has_staff_permission(user, "rescue_manage")


async def require_cskh_or_owner(
    user: User = Depends(get_current_user),
) -> User:
    if not is_rescue_staff(user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Bạn cần quyền quản lý trạm cứu hộ để thực hiện thao tác này.",
        )
    return user


async def require_post_owner_or_cskh(
    post_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CommunityPost:
    post = await session.get(CommunityPost, post_id)
    if not post:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tin cứu hộ.")
    if post.author_user_id != user.id and not is_rescue_staff(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền thực hiện thao tác này.")
    return post


def require_post_owner(
    post: CommunityPost,
    user: User,
) -> None:
    if post.author_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Chỉ người đăng tin mới được thực hiện thao tác này.")
