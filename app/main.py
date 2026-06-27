from __future__ import annotations

from fastapi import FastAPI

from app.config import get_settings
from app.logging import configure_logging, safe_request_logging_middleware
from app.routers.health import router as health_router


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="IBB Insurance Portal API")
    app.middleware("http")(safe_request_logging_middleware)
    app.include_router(health_router)
    return app


app = create_app()
