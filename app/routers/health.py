from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Response, status
from redis.asyncio import Redis
from sqlalchemy import create_engine, func, select, text

from app.config import get_settings
from app.models import bitrix_categories, bitrix_stage_mappings, languages, product_groups, roles
from app.reference_data import REQUIRED_REFERENCE_CODES

router = APIRouter(tags=["health"])
logger = logging.getLogger("ibb_portal.health")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": get_settings().service_name}


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


async def check_database() -> str:
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
        return "ok"
    finally:
        engine.dispose()


async def check_redis() -> str:
    client = Redis.from_url(get_settings().redis_url, socket_connect_timeout=2, socket_timeout=2)
    try:
        await client.ping()
        return "ok"
    finally:
        await client.aclose()


async def check_migrations() -> str:
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            version = connection.execute(text("select version_num from alembic_version")).scalar_one_or_none()
            return "ok" if version else "error"
    finally:
        engine.dispose()


async def check_reference_data() -> str:
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            checks = [
                connection.execute(
                    select(func.count()).select_from(roles).where(roles.c.code.in_(REQUIRED_REFERENCE_CODES["roles"]))
                ).scalar_one()
                == len(REQUIRED_REFERENCE_CODES["roles"]),
                connection.execute(
                    select(func.count())
                    .select_from(languages)
                    .where(languages.c.code.in_(REQUIRED_REFERENCE_CODES["languages"]))
                ).scalar_one()
                == len(REQUIRED_REFERENCE_CODES["languages"]),
                connection.execute(
                    select(func.count())
                    .select_from(product_groups)
                    .where(product_groups.c.code.in_(REQUIRED_REFERENCE_CODES["product_groups"]))
                ).scalar_one()
                == len(REQUIRED_REFERENCE_CODES["product_groups"]),
                connection.execute(
                    select(func.count())
                    .select_from(bitrix_categories)
                    .where(bitrix_categories.c.bitrix_category_id.in_(REQUIRED_REFERENCE_CODES["bitrix_categories"]))
                ).scalar_one()
                == len(REQUIRED_REFERENCE_CODES["bitrix_categories"]),
                connection.execute(select(func.count()).select_from(bitrix_stage_mappings)).scalar_one() >= 20,
            ]
        return "ok" if all(checks) else "error"
    finally:
        engine.dispose()


async def run_check(name: str, check) -> str:
    started = time.perf_counter()
    try:
        result = await check()
    except Exception:
        result = "error"
        error_code = f"{name.upper()}_CHECK_FAILED"
        logger.warning(
            "health_check_failed",
            extra={
                "check": name,
                "status": result,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "error_code": error_code,
            },
        )
    return result


@router.get("/health/ready")
async def ready(response: Response) -> dict[str, object]:
    checks = {
        "database": await run_check("database", check_database),
        "redis": await run_check("redis", check_redis),
        "migrations": await run_check("migrations", check_migrations),
        "reference_data": await run_check("reference_data", check_reference_data),
    }
    is_ok = all(value == "ok" for value in checks.values())
    if not is_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if is_ok else "error", "checks": checks}
