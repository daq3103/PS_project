from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.csrf import CsrfMiddleware
from app.core.redis import close_redis
from app.core.staff_totp import StaffTotpMiddleware
from app.modules.admin.router import router as admin_router
from app.modules.analytics.metrics import MetricsMiddleware
from app.modules.analytics.router import admin_router as analytics_admin_router
from app.modules.analytics.router import router as analytics_router
from app.modules.cart.router import router as cart_router
from app.modules.catalog.router import router as catalog_router
from app.modules.community.admin_router import router as community_admin_router
from app.modules.community.guards import CommunityMiddleware
from app.modules.community.router import router as community_router
from app.modules.customer.address_router import router as address_router
from app.modules.customer.router import router as auth_router
from app.modules.order.router import router as order_router
from app.modules.payment.router import router as payment_webhook_router
from app.modules.shipping.router import router as shipping_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_redis()


settings = get_settings()

app = FastAPI(
    title="Petshop API",
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
app.add_middleware(StaffTotpMiddleware)
app.add_middleware(CommunityMiddleware)
app.add_middleware(MetricsMiddleware)

app.include_router(catalog_router)
app.include_router(auth_router)
app.include_router(address_router)
app.include_router(cart_router)
app.include_router(order_router)
app.include_router(payment_webhook_router)
app.include_router(shipping_router)
app.include_router(community_router)
app.include_router(admin_router)
app.include_router(community_admin_router)
app.include_router(analytics_router)
app.include_router(analytics_admin_router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ready"}
