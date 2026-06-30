from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
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
    bitrix24_base_url: str | None = Field(default=None, alias="BITRIX24_BASE_URL")
    bitrix24_webhook_token: str | None = Field(default=None, alias="BITRIX24_WEBHOOK_TOKEN")
    bitrix24_webhook_url: str | None = Field(default=None, alias="BITRIX24_WEBHOOK_URL")
    bitrix24_timeout_seconds: int = Field(default=15, alias="BITRIX24_TIMEOUT_SECONDS")
    bitrix24_max_retries: int = Field(default=3, alias="BITRIX24_MAX_RETRIES")
    bitrix24_retry_backoff_seconds: float = Field(default=2.0, alias="BITRIX24_RETRY_BACKOFF_SECONDS")
    bitrix24_enabled: bool = Field(default=False, alias="BITRIX24_ENABLED")
    bitrix_outbound_webhook_secret: str = Field(default="replace_me", alias="BITRIX_OUTBOUND_WEBHOOK_SECRET")
    portal_public_url: str = Field(default="http://localhost:3000", alias="PORTAL_PUBLIC_URL")
    frontend_base_url: str | None = Field(default=None, alias="FRONTEND_BASE_URL")
    invite_token_ttl_hours: int = Field(default=48, alias="INVITE_TOKEN_TTL_HOURS")
    first_login_token_ttl_hours: int = Field(default=24, alias="FIRST_LOGIN_TOKEN_TTL_HOURS")
    password_reset_token_ttl_minutes: int = Field(default=30, alias="PASSWORD_RESET_TOKEN_TTL_MINUTES")
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
    document_temp_storage_path: str = Field(default="storage/application-documents", alias="DOCUMENT_TEMP_STORAGE_PATH")
    document_temp_retention_hours: int = Field(default=24, alias="DOCUMENT_TEMP_RETENTION_HOURS")
    bitrix_document_folder_id: int | None = Field(default=None, alias="BITRIX_DOCUMENT_FOLDER_ID")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    service_name: str = "ibb-portal-backend"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("bitrix_document_folder_id", mode="before")
    @classmethod
    def empty_folder_id_is_none(cls, value: object) -> object:
        if value in {"", "replace_me", "replace-me"}:
            return None
        return value

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

    @property
    def resolved_frontend_base_url(self) -> str:
        return self.frontend_base_url or self.portal_public_url

    @property
    def resolved_bitrix24_base_url(self) -> str | None:
        if not self._is_placeholder(self.bitrix24_base_url):
            return self.bitrix24_base_url
        parsed = self._split_bitrix24_webhook_url()
        return parsed[0] if parsed else None

    @property
    def resolved_bitrix24_webhook_token(self) -> str | None:
        if not self._is_placeholder(self.bitrix24_webhook_token):
            return self.bitrix24_webhook_token
        parsed = self._split_bitrix24_webhook_url()
        return parsed[1] if parsed else None

    def _split_bitrix24_webhook_url(self) -> tuple[str, str] | None:
        if self._is_placeholder(self.bitrix24_webhook_url):
            return None
        url = str(self.bitrix24_webhook_url).strip().rstrip("/")
        marker = "/rest/"
        if marker not in url:
            return None
        prefix, rest_tail = url.split(marker, maxsplit=1)
        parts = [part for part in rest_tail.split("/") if part]
        if len(parts) < 2:
            return None
        return f"{prefix}{marker}{parts[0]}", parts[1]


@lru_cache
def get_settings() -> Settings:
    return Settings()
