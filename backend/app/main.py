from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.admin.reporting_router import router as reporting_router
from app.modules.admin.shop_finance_router import router as shop_finance_router
from app.modules.admin.archive_router import router as archive_router
from app.core.config import get_settings
from app.core.csrf import CsrfMiddleware
from app.core.redis import close_redis
from app.modules.admin.operations_router import router as operations_router
from app.modules.admin.router import router as admin_router
from app.modules.admin.staff_router import router as staff_admin_router
from app.modules.analytics.metrics import MetricsMiddleware
from app.modules.analytics.router import admin_router as analytics_admin_router
from app.modules.analytics.router import router as analytics_router
from app.modules.cart.router import router as cart_router
from app.modules.catalog.router import router as catalog_router
from app.modules.catalog.navigation import router as shop_navigation_router
from app.modules.community.admin_router import router as community_admin_router
from app.modules.community.guards import CommunityMiddleware
from app.modules.community.router import router as community_router
from app.modules.customer.address_router import router as address_router
from app.modules.customer.router import router as auth_router
from app.modules.order.router import router as order_router
from app.modules.order.support_router import router as support_router
from app.modules.payment.router import router as payment_webhook_router
from app.modules.rescue.asset_router import router as rescue_asset_router
from app.modules.rescue.audit_router import router as rescue_audit_router
from app.modules.rescue.contributions import router as rescue_contribution_router
from app.modules.rescue.message_router import router as rescue_message_router
from app.modules.rescue.router import router as rescue_router
from app.modules.rescue.workflow_router import router as rescue_workflow_router
from app.modules.shipping.router import router as shipping_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_redis()


settings = get_settings()

app = FastAPI(
    title="PetHome API",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CsrfMiddleware)
app.add_middleware(CommunityMiddleware)
app.add_middleware(MetricsMiddleware)

app.include_router(catalog_router)
app.include_router(shop_navigation_router)
app.include_router(auth_router)
app.include_router(address_router)
app.include_router(cart_router)
app.include_router(order_router)
app.include_router(payment_webhook_router)
app.include_router(shipping_router)
app.include_router(rescue_audit_router)
app.include_router(rescue_message_router)
app.include_router(rescue_workflow_router)
app.include_router(rescue_asset_router)
app.include_router(rescue_contribution_router)
app.include_router(rescue_router)
app.include_router(support_router)
app.include_router(operations_router)
app.include_router(community_router)
app.include_router(admin_router)
app.include_router(archive_router)
app.include_router(reporting_router)
app.include_router(shop_finance_router)
app.include_router(staff_admin_router)
app.include_router(community_admin_router)
app.include_router(analytics_router)
app.include_router(analytics_admin_router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    import asyncio

    from fastapi import HTTPException

    from app.core.redis import redis_cache, redis_queue
    from app.modules.analytics.system import database_probe
    async def probe():
        await database_probe()
        await redis_cache.ping()
        await redis_queue.ping()
    try:
        await asyncio.wait_for(probe(), timeout=3)
    except Exception as exc:
        raise HTTPException(503, "Hệ thống đang kết nối lại. Vui lòng thử sau.") from exc
    return {"status": "ready"}


@app.middleware("http")
async def rescue_response_headers(request, call_next):
    if request.url.path.startswith(("/api/v1/rescue/", "/api/v1/admin/rescue/")):
        import secrets
        request.state.rescue_request_id = secrets.token_hex(12)
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.rescue_request_id
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    return await call_next(request)
