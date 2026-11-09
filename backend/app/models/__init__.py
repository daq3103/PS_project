"""SQLAlchemy models — import all so Alembic can discover metadata."""

from app.models.admin_archive import AdminArchive
from app.models.shop_expense import ShopExpense, ShopExpenseReceipt
from app.models.navigation import ShopNavigationSettings
from app.models.analytics import AnalyticsEvent
from app.models.rescue import RescuePublication
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
from app.models.operations import (
    CheckoutQuote,
    CommerceJob,
    OperationCase,
    SupportMessage,
    SupportTicket,
)
from app.models import rescue_workflow as rescue_workflow
from app.models.rescue import (
    RescueAnimal,
    RescueAudit,
    RescueCase,
    RescueEpisode,
    RescueEvent,
    RescueExpense,
    RescueFund,
    RescueLedger,
    RescueLocation,
    RescueReceipt,
    RescueReport,
    RescueSupply,
    RescueTask,
)
from app.models.user import CustomerAddress, PasswordResetToken, RefreshToken, StaffRoleChange, User

__all__ = [
    "ShopExpense",
    "ShopExpenseReceipt",
    "ShopNavigationSettings",
    "RescuePublication",
    "RescueAnimal", "RescueLocation", "RescueCase", "RescueEpisode", "RescueEvent", "RescueTask", "RescueReport", "RescueReceipt", "RescueAudit", "RescueFund", "RescueLedger", "RescueExpense", "RescueSupply",
    "CommerceJob", "OperationCase", "CheckoutQuote", "SupportTicket", "SupportMessage",
    "AnalyticsEvent",
    "AdoptionRequest",
    "CommunityNotification",
    "CommunityReceipt",
    "User",
    "CustomerAddress",
    "RefreshToken",
    "PasswordResetToken",
    "StaffRoleChange",
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
