from __future__ import annotations

import pytest

from app.config import Settings
from app.email import send_invite_email


def make_settings(**overrides) -> Settings:
    values = {
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "REDIS_URL": "redis://localhost:6379/15",
        "JWT_SECRET": "test_jwt_secret_with_minimum_32_bytes",
        "COOKIE_SECRET": "test_cookie_secret_with_minimum_32_bytes",
    }
    values.update(overrides)
    return Settings(**values)


def test_bitrix24_webhook_alias_is_used_when_canonical_name_is_placeholder() -> None:
    settings = make_settings(
        BITRIX_WEBHOOK_URL="replace_me",
        BITRIX24_WEBHOOK_URL="https://b24.example.invalid/rest/1/test-webhook",
    )

    assert settings.resolved_bitrix_webhook_url == "https://b24.example.invalid/rest/1/test-webhook"


def test_smtp_aliases_and_implicit_ssl_are_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    class FakeSmtp:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            calls["connect"] = {"host": host, "port": port, "timeout": timeout}
            calls["used_ssl"] = True

        def __enter__(self) -> FakeSmtp:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def starttls(self) -> None:
            calls["starttls"] = True

        def login(self, username: str, password: str) -> None:
            calls["login"] = {"username": username, "password": password}

        def send_message(self, message) -> None:
            calls["from"] = message["From"]
            calls["to"] = message["To"]

    def fail_plain_smtp(*_args, **_kwargs):
        raise AssertionError("plain SMTP must not be used when SMTP_SECURE=true")

    monkeypatch.setattr("app.email.smtplib.SMTP_SSL", FakeSmtp)
    monkeypatch.setattr("app.email.smtplib.SMTP", fail_plain_smtp)

    settings = make_settings(
        SMTP_HOST="smtp.example.invalid",
        SMTP_PORT=465,
        SMTP_USERNAME="replace_me",
        SMTP_USER="alias-user@example.invalid",
        SMTP_PASSWORD="replace_me",
        SMTP_PASS="alias-password",
        SMTP_FROM_EMAIL="replace_me@example.com",
        SMTP_FROM="sender@example.invalid",
        SMTP_SECURE=True,
        SMTP_USE_TLS=True,
    )

    send_invite_email(
        to_email="recipient@example.invalid",
        invite_link="https://portal.example.invalid/invite?token=test",
        temporary_password="temporary-password",
        settings=settings,
    )

    assert calls["connect"] == {"host": "smtp.example.invalid", "port": 465, "timeout": 10}
    assert calls["login"] == {"username": "alias-user@example.invalid", "password": "alias-password"}
    assert calls["from"] == "sender@example.invalid"
    assert calls["to"] == "recipient@example.invalid"
    assert "starttls" not in calls
