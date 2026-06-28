from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.logging import configure_logging, safe_request_logging_middleware
from app.routers.applications import router as applications_router
from app.routers.auth import AuthError
from app.routers.auth import router as auth_router
from app.routers.auto_applications import router as auto_applications_router
from app.routers.bitrix_webhooks import router as bitrix_webhooks_router
from app.routers.company_access import router as company_access_router
from app.routers.documents import router as documents_router
from app.routers.health import router as health_router
from app.routers.policies import router as policies_router


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="IBB Insurance Portal API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["content-type", "x-request-id"],
    )
    app.middleware("http")(safe_request_logging_middleware)

    @app.exception_handler(AuthError)
    async def auth_error_handler(_request, exc: AuthError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)

    app.include_router(auth_router)
    app.include_router(auto_applications_router)
    app.include_router(applications_router)
    app.include_router(bitrix_webhooks_router)
    app.include_router(company_access_router)
    app.include_router(documents_router)
    app.include_router(health_router)
    app.include_router(policies_router)
    return app


app = create_app()
