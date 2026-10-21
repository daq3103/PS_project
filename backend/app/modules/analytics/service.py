"""Anonymous first-party events; never persist URLs, queries, IPs or raw identifiers."""

import hashlib
import hmac
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.analytics import AnalyticsEvent
from app.modules.analytics.schemas import EventIn

ZONE = ZoneInfo("Asia/Ho_Chi_Minh")
EXACT_PAGES = {
    "/",
    "/search",
    "/cart",
    "/checkout",
    "/track-order",
    "/login",
    "/register",
    "/account",
    "/account/profile",
    "/account/orders",
    "/account/addresses",
    "/account/community",
    "/account/adoption-requests",
    "/tram-cuu-ho",
    "/tram-cuu-ho/dang-tin",
}


def normalize_page(path: str) -> tuple[str, str] | None:
    # Only bounded route templates are stored. Query values may contain phone numbers or tokens.
    path = path.split("?", 1)[0].split("#", 1)[0].rstrip("/") or "/"
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        return None
    if path in EXACT_PAGES:
        page = path
    elif path.startswith("/p/"):
        page = "/p/[product]"
    elif path.startswith("/c/"):
        page = "/c/[category]"
    elif path.startswith("/tram-cuu-ho/"):
        page = "/tram-cuu-ho/[post]"
    elif path.startswith("/account/community/") and path.endswith("/edit"):
        page = "/account/community/[post]/edit"
    else:
        return None
    section = (
        "rescue"
        if page.startswith(("/tram-cuu-ho", "/account/community", "/account/adoption"))
        else "shop"
    )
    if page in {"/account", "/account/profile", "/account/addresses", "/login", "/register"}:
        section = "account"
    return page, section


def digest(value: str) -> str:
    return hmac.new(
        get_settings().jwt_secret.encode(), ("analytics:" + value).encode(), hashlib.sha256
    ).hexdigest()


async def save_event(session: AsyncSession, event: EventIn, page: str, section: str) -> None:
    values = dict(
        event_id=event.event_id,
        kind=event.kind,
        visitor_hash=digest(str(event.visitor_id)),
        session_hash=digest(str(event.session_id)),
        page=page,
        section=section,
        source=event.source,
        device=event.device,
        value=event.value,
    )
    stmt = insert(AnalyticsEvent).values(**values)
    # Retries never inflate pageviews. Web Vitals may report newer final values for the same document.
    if event.kind == "page_view":
        stmt = stmt.on_conflict_do_nothing()
    else:
        stmt = stmt.on_conflict_do_update(
            index_elements=[AnalyticsEvent.event_id, AnalyticsEvent.kind],
            set_={"value": stmt.excluded.value},
            where=(AnalyticsEvent.visitor_hash == values["visitor_hash"])
            & (AnalyticsEvent.session_hash == values["session_hash"]),
        )
    await session.execute(stmt)


async def traffic_report(session: AsyncSession, days: int, section: str) -> dict:
    today = datetime.now(ZONE).date()
    start = datetime.combine(today - timedelta(days=days - 1), time.min, ZONE)
    params = {"start": start, "section": section}
    base = "FROM analytics_events WHERE created_at >= :start AND (:section = 'all' OR section = :section)"
    summary = (
        (
            await session.execute(
                text(
                    """SELECT count(*) AS views,
        count(DISTINCT visitor_hash) AS visitors, count(DISTINCT session_hash) AS sessions
        """
                    + base
                    + " AND kind = 'page_view'"
                ),
                params,
            )
        )
        .mappings()
        .one()
    )
    daily_rows = (
        (
            await session.execute(
                text(
                    """SELECT
        (created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS day, count(*) AS views,
        count(DISTINCT visitor_hash) AS visitors, count(DISTINCT session_hash) AS sessions
        """
                    + base
                    + " AND kind = 'page_view' GROUP BY 1 ORDER BY 1"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )
    by_day = {row["day"]: dict(row) for row in daily_rows}
    daily = [
        by_day.get(
            start.date() + timedelta(days=i),
            {
                "day": start.date() + timedelta(days=i),
                "views": 0,
                "visitors": 0,
                "sessions": 0,
            },
        )
        for i in range(days)
    ]
    dimensions = {}
    for column in ("page", "source", "device", "section"):
        # Fixed, internal column list; no request-controlled SQL identifiers.
        rows = (
            (
                await session.execute(
                    text(
                        f"SELECT {column} AS label, count(*) AS count "
                        + base
                        + f" AND kind = 'page_view' GROUP BY {column} ORDER BY count(*) DESC LIMIT 20"
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        dimensions[column] = [dict(row) for row in rows]
    vitals = (
        (
            await session.execute(
                text(
                    """SELECT kind, count(*) AS samples,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75,
        avg(value) AS average """
                    + base
                    + " AND kind != 'page_view' GROUP BY kind"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )
    return {
        "summary": dict(summary),
        "daily": daily,
        "dimensions": dimensions,
        "vitals": [dict(row) for row in vitals],
        "days": days,
        "section": section,
        "timezone": "Asia/Ho_Chi_Minh",
        "retention_days": get_settings().analytics_retention_days,
        "generated_at": datetime.now(UTC),
    }


async def cleanup_analytics(ctx: dict) -> dict:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        removed = (
            delete(AnalyticsEvent)
            .where(
                AnalyticsEvent.created_at
                < datetime.now(UTC) - timedelta(days=get_settings().analytics_retention_days)
            )
            .returning(AnalyticsEvent.event_id)
            .cte("removed")
        )
        count = await session.scalar(select(func.count()).select_from(removed))
        await session.commit()
    return {"deleted": count}
