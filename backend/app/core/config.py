from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://petshop:petshop@localhost:5432/petshop"
    redis_cache_url: str = "redis://localhost:6379/0"
    redis_cache_password: str = ""
    redis_queue_url: str = "redis://localhost:6380/0"
    redis_queue_password: str = ""

    jwt_secret: str = "change_me_jwt_secret_min_32_chars_xxxxxxxxxxxx"
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 30
    jwt_clock_skew_seconds: int = Field(default=30, ge=0, le=60)

    # 64 hex chars = 32 bytes for AES-256-GCM
    secret_encryption_key: str = ""

    revalidate_secret: str = "change_me"
    nextjs_revalidate_url: str = "http://localhost:3000/api/revalidate"

    app_public_url: str = ""
    google_client_id: str = ""
    password_reset_email_provider: Literal["resend", "gmail"] = "resend"
    gmail_user: str = ""
    gmail_app_password: SecretStr = SecretStr("")
    resend_api_key: str = ""
    resend_from: str = ""
    payment_provider: str = "payos"
    rescue_donations_enabled: bool = False
    rescue_automation_paused: bool = False
    rescue_recipient_name: str = ""
    rescue_bank_name: str = ""
    rescue_bank_account: str = ""
    rescue_merchant_id: str = ""
    rescue_webhook_secret: str = ""
    rescue_fund_policy_confirmed: bool = False
    payos_client_id: str = ""
    payos_api_key: str = ""
    payos_checksum_key: str = ""
    shipping_base_fee: int = Field(default=25000, ge=0, le=10000000)
    shipping_per_kg_fee: int = Field(default=5000, ge=0, le=1000000)

    # Webhook secrets
    mock_vietqr_webhook_secret: str = ""
    mock_ghn_webhook_secret: str = ""

    cors_origins: str = "http://localhost:3000,http://localhost"
    tz: str = "Asia/Ho_Chi_Minh"

    community_upload_dir: str = "/app/data/community-uploads"
    max_community_upload_bytes: int = 5 * 1024 * 1024  # 5 MB
    community_enabled: bool = True
    community_turnstile_site_key: str = ""
    community_turnstile_secret: str = ""
    community_turnstile_hostname: str = ""
    community_retention_days: int = Field(default=90, ge=1, le=3650)
    # Only configure actual reverse proxy subnets. Empty trusts no forwarded headers.
    trusted_proxy_cidrs: str = ""
    analytics_enabled: bool = True
    analytics_retention_days: int = Field(default=90, ge=30, le=365)

    # SQLAlchemy pool (4 workers × ~10 + headroom for cron ≤ max_connections=120)
    db_pool_size: int = 10
    db_max_overflow: int = 5
    inventory_min_shelf_life_days: int = Field(default=0, ge=0, le=3650)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @staticmethod
    def _inject_password(url: str, password: str) -> str:
        if not password:
            return url
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            return url
        return f"{scheme}://:{password}@{rest}"

    @property
    def redis_cache_url_with_auth(self) -> str:
        return self._inject_password(self.redis_cache_url, self.redis_cache_password)

    @property
    def redis_queue_url_with_auth(self) -> str:
        return self._inject_password(self.redis_queue_url, self.redis_queue_password)


@lru_cache
def get_settings() -> Settings:
    return Settings()
