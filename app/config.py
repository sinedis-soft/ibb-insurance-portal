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
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    service_name: str = "ibb-portal-backend"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"prod", "production"}

    @property
    def secure_cookies(self) -> bool:
        return self.auth_cookie_secure if self.auth_cookie_secure is not None else self.is_production

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
