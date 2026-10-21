"""Analytics privacy, real PostgreSQL aggregation, telemetry isolation and owner authorization."""

import os
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select, update

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import require_owner
from app.models.analytics import AnalyticsEvent
from app.modules.analytics import metrics, service
from app.modules.analytics.schemas import EventIn


def payload(**changes):
    return EventIn(
        **(
            {
                "event_id": uuid.uuid4(),
                "visitor_id": uuid.uuid4(),
                "session_id": uuid.uuid4(),
                "path": "/p/cat?phone=0901234567",
            }
            | changes
        )
    )


def test_privacy_templates_and_metric_validation():
    assert service.normalize_page("/p/private-phone?token=secret") == ("/p/[product]", "shop")
    assert service.normalize_page("/tram-cuu-ho/meo") == ("/tram-cuu-ho/[post]", "rescue")
    for path in ("/admin/orders", "//evil.test", "/unknown/personal", "https://evil.test"):
        assert service.normalize_page(path) is None
    for changes in (
        {"kind": "INP"},
        {"kind": "CLS", "value": 200},
        {"value": float("nan")},
        {"email": "private@example.test"},
    ):
        with pytest.raises(ValidationError):
            payload(**changes)
    assert len(service.digest("test")) == 64
    assert service.digest("test") != "test"


@pytest.mark.asyncio
async def test_telemetry_failure_never_breaks_response(monkeypatch):
    class BrokenRedis:
        def pipeline(self):
            raise RuntimeError("offline")

    monkeypatch.setattr(metrics, "redis_cache", BrokenRedis())
    monkeypatch.setattr(metrics, "_retry_at", 0)
    await metrics.record_request("GET /api/v1/products/{id}", 500, 10)
    assert metrics._retry_at > 0


@pytest.mark.asyncio
async def test_api_metric_labels_are_bounded_and_include_failures(monkeypatch):
    captured = []

    async def record(route, status, duration):
        captured.append((route, status, duration))

    async def target(scope, receive, send):
        scope["route"] = SimpleNamespace(path="/api/v1/products/{product_id}")
        await send({"type": "http.response.start", "status": 503, "headers": []})
        await send({"type": "http.response.body", "body": b"failed"})

    monkeypatch.setattr(metrics, "record_request", record)
    transport = httpx.ASGITransport(app=metrics.MetricsMiddleware(target))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.request(
            "UNBOUNDED_CUSTOM_METHOD", "/api/v1/products/private-id?token=secret"
        )
    assert result.status_code == 503
    assert captured[0][0] == "OTHER /api/v1/products/{product_id}"
    assert captured[0][1] == 503 and captured[0][2] >= 0


@pytest.mark.asyncio
async def test_owner_authorization_without_database():
    from app.main import app

    async def deny():
        raise HTTPException(403, "Owner access required")

    app.dependency_overrides[require_owner] = deny
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            assert (await client.get("/api/v1/admin/analytics/system")).status_code == 403
            assert (await client.get("/api/v1/analytics/config")).json()["enabled"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("COMMUNITY_TEST_DATABASE"), reason="Requires isolated test database"
)
async def test_event_idempotency_counts_privacy_and_retention(monkeypatch):
    from test_community import sessions

    factory = sessions()
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", factory)
    event = payload()
    async with factory() as session:
        await service.save_event(session, event, *service.normalize_page(event.path))
        await service.save_event(session, event, *service.normalize_page(event.path))
        other = payload(
            visitor_id=event.visitor_id, session_id=event.session_id, path="/tram-cuu-ho"
        )
        await service.save_event(session, other, *service.normalize_page(other.path))
        for value in (250, 400):
            vital = event.model_copy(update={"kind": "LCP", "value": value})
            await service.save_event(session, vital, *service.normalize_page(event.path))
        await session.commit()
    async with factory() as session:
        all_rows = list(await session.scalars(select(AnalyticsEvent)))
        assert len(all_rows) == 3
        assert all("0901234567" not in row.page and "?" not in row.page for row in all_rows)
        assert all(str(event.visitor_id) != row.visitor_hash for row in all_rows)
        report = await service.traffic_report(session, 7, "all")
        assert report["summary"] == {"views": 2, "visitors": 1, "sessions": 1}
        assert report["vitals"][0]["p75"] == 400
        assert len(report["daily"]) == 7
        rescue = await service.traffic_report(session, 1, "rescue")
        assert rescue["summary"]["views"] == 1
        assert sum(day["views"] for day in report["daily"]) == 2
        await session.execute(
            update(AnalyticsEvent).values(created_at=datetime.now(UTC) - timedelta(days=100))
        )
        await session.commit()
    result = await service.cleanup_analytics({})
    assert result["deleted"] == 3


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("COMMUNITY_TEST_DATABASE"), reason="Requires isolated test database"
)
async def test_ingestion_routes_flags_dnt_and_no_store():
    from test_community import sessions

    from app.main import app

    factory = sessions()

    async def database():
        async with factory() as session:
            yield session
            await session.commit()

    async def owner():
        return None

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[require_owner] = owner
    settings = get_settings()
    previous = settings.analytics_enabled
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for path, headers in [
                ("/admin/orders", {}),
                ("/p/cat", {"DNT": "1"}),
                ("/p/cat", {"Sec-GPC": "1"}),
            ]:
                result = await client.post(
                    "/api/v1/analytics/events",
                    json=payload(path=path).model_dump(mode="json"),
                    headers=headers,
                )
                assert result.status_code == 204
            event = payload(path="/tram-cuu-ho")
            for _ in range(2):
                result = await client.post(
                    "/api/v1/analytics/events", json=event.model_dump(mode="json")
                )
                assert result.status_code == 204
                assert result.headers["cache-control"] == "no-store"
            heartbeat = event.model_copy(update={"kind": "heartbeat"})
            assert (
                await client.post(
                    "/api/v1/analytics/events", json=heartbeat.model_dump(mode="json")
                )
            ).status_code == 204
            result = await client.get("/api/v1/admin/analytics/traffic?days=7&section=rescue")
            assert result.status_code == 200
            assert result.json()["summary"]["views"] == 1
            assert result.headers["cache-control"] == "no-store"
            assert (
                await client.get("/api/v1/admin/analytics/traffic?days=1000")
            ).status_code == 422
            settings.analytics_enabled = False
            assert (
                await client.post(
                    "/api/v1/analytics/events", json=payload().model_dump(mode="json")
                )
            ).status_code == 204
            async with factory() as session:
                assert await session.scalar(select(func.count()).select_from(AnalyticsEvent)) == 1
    finally:
        settings.analytics_enabled = previous
        app.dependency_overrides.clear()
        from app.core.redis import redis_cache

        await redis_cache.aclose()
