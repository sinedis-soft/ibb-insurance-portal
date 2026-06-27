from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    jwt_secret: str = Field(alias="JWT_SECRET")
    cookie_secret: str = Field(alias="COOKIE_SECRET")
    app_env: str = Field(default="local", alias="APP_ENV")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")
    access_token_ttl_minutes: int = Field(default=15, alias="AUTH_ACCESS_TTL_MINUTES")
    refresh_token_ttl_days: int = Field(default=14, alias="AUTH_REFRESH_TTL_DAYS")
    auth_cookie_secure: bool | None = Field(default=None, alias="AUTH_COOKIE_SECURE")
    bitrix_webhook_url: str = Field(default="replace_me", alias="BITRIX_WEBHOOK_URL")
    bitrix24_webhook_url: str | None = Field(default=None, alias="BITRIX24_WEBHOOK_URL")
    bitrix_timeout_seconds: int = Field(default=10, alias="BITRIX_TIMEOUT_SECONDS")
    bitrix_outbound_webhook_secret: str = Field(default="replace_me", alias="BITRIX_OUTBOUND_WEBHOOK_SECRET")
    portal_public_url: str = Field(default="http://localhost:3000", alias="PORTAL_PUBLIC_URL")
    invite_token_ttl_hours: int = Field(default=48, alias="INVITE_TOKEN_TTL_HOURS")
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_user: str | None = Field(default=None, alias="SMTP_USER")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_pass: str | None = Field(default=None, alias="SMTP_PASS")
    smtp_from_email: str | None = Field(default=None, alias="SMTP_FROM_EMAIL")
    smtp_from: str | None = Field(default=None, alias="SMTP_FROM")
    smtp_secure: bool = Field(default=False, alias="SMTP_SECURE")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    service_name: str = "ibb-portal-backend"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @staticmethod
    def _is_placeholder(value: str | None) -> bool:
        return value in {None, "", "replace_me", "replace_me@example.com"}

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"prod", "production"}

    @property
    def secure_cookies(self) -> bool:
        return self.auth_cookie_secure if self.auth_cookie_secure is not None else self.is_production

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def resolved_bitrix_webhook_url(self) -> str:
        if not self._is_placeholder(self.bitrix_webhook_url):
            return self.bitrix_webhook_url
        return self.bitrix24_webhook_url or "replace_me"

    @property
    def resolved_smtp_username(self) -> str | None:
        return self.smtp_username if not self._is_placeholder(self.smtp_username) else self.smtp_user

    @property
    def resolved_smtp_password(self) -> str | None:
        return self.smtp_password if not self._is_placeholder(self.smtp_password) else self.smtp_pass

    @property
    def resolved_smtp_from_email(self) -> str | None:
        return self.smtp_from_email if not self._is_placeholder(self.smtp_from_email) else self.smtp_from

    @property
    def email_enabled(self) -> bool:
        return bool(not self._is_placeholder(self.smtp_host) and self.resolved_smtp_from_email)


@lru_cache
def get_settings() -> Settings:
    return Settings()
