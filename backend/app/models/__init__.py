"""SQLAlchemy models — import all so Alembic can discover metadata."""

from app.models.analytics import AnalyticsEvent
from app.models.catalog import Category, Product, ProductImage, ProductVariant, Review
from app.models.commerce import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    OrderStatusHistory,
    Promotion,
    PromotionUsage,
)
from app.models.community import (
    AdoptionRequest,
    CommunityAuditLog,
    CommunityJobOutbox,
    CommunityNotification,
    CommunityPost,
    CommunityPostImage,
    CommunityReceipt,
    CommunityReport,
    CommunityUpload,
)
from app.models.fulfillment import CarrierAccount, Fulfillment, Payment, WebhookEvent
from app.models.inventory import InventoryLot, LotAllocation, ReturnedStock, StockMovement
from app.models.user import CustomerAddress, RefreshToken, User

__all__ = [
    "AnalyticsEvent",
    "AdoptionRequest",
    "CommunityNotification",
    "CommunityReceipt",
    "User",
    "CustomerAddress",
    "RefreshToken",
    "Category",
    "Product",
    "ProductVariant",
    "ProductImage",
    "Review",
    "CommunityPost",
    "CommunityPostImage",
    "CommunityUpload",
    "CommunityReport",
    "CommunityAuditLog",
    "CommunityJobOutbox",
    "InventoryLot",
    "StockMovement",
    "LotAllocation",
    "ReturnedStock",
    "Cart",
    "CartItem",
    "Promotion",
    "PromotionUsage",
    "Order",
    "OrderItem",
    "OrderStatusHistory",
    "Payment",
    "CarrierAccount",
    "Fulfillment",
    "WebhookEvent",
]
