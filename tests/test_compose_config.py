from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_compose() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def test_compose_defines_required_runtime_services() -> None:
    compose = load_compose()
    services = compose["services"]

    assert {"backend", "frontend", "postgres", "redis"}.issubset(services)
    assert {"migrate", "seed"}.issubset(services)
    assert "postgres_data" in compose["volumes"]
    assert "redis_data" not in compose.get("volumes", {})


def test_frontend_receives_only_public_runtime_configuration() -> None:
    frontend_env = load_compose()["services"]["frontend"]["environment"]

    assert set(frontend_env) == {"NEXT_PUBLIC_API_BASE_URL"}
    assert "DATABASE_URL" not in frontend_env
    assert "REDIS_URL" not in frontend_env
    assert "JWT_SECRET" not in frontend_env
    assert "COOKIE_SECRET" not in frontend_env
    assert "BITRIX_WEBHOOK_URL" not in frontend_env
    assert "BITRIX24_WEBHOOK_TOKEN" not in frontend_env


def test_env_example_contains_local_placeholders_without_real_webhooks() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "POSTGRES_PASSWORD=change_me_local_only" in env_example
    assert "JWT_SECRET=change_me_local_only" in env_example
    assert "COOKIE_SECRET=change_me_local_only" in env_example
    assert "BITRIX24_BASE_URL=replace_me" in env_example
    assert "BITRIX24_WEBHOOK_TOKEN=replace_me" in env_example
    assert "BITRIX24_ENABLED=false" in env_example
    assert "BITRIX_WEBHOOK_URL" not in env_example
    assert "https://" not in env_example
    assert "access_token" not in env_example.lower()
