"""Authorization helpers for the community rescue module."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.community import CommunityPost
from app.models.user import User

RESCUE_STAFF_ROLES = frozenset({"owner", "cskh_staff"})


def is_rescue_staff(user: User) -> bool:
    return user.role in RESCUE_STAFF_ROLES


async def require_cskh_or_owner(
    user: User = Depends(get_current_user),
) -> User:
    if not is_rescue_staff(user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Rescue staff access required",
        )
    return user


async def require_post_owner_or_cskh(
    post_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CommunityPost:
    post = await session.get(CommunityPost, post_id)
    if not post:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.author_user_id != user.id and not is_rescue_staff(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not allowed")
    return post


def require_post_owner(
    post: CommunityPost,
    user: User,
) -> None:
    if post.author_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not the post owner")
