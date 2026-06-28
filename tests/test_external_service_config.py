from __future__ import annotations

import pytest

from app.config import Settings
from app.email import build_invite_email_message, send_invite_email


def make_settings(**overrides) -> Settings:
    values = {
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "REDIS_URL": "redis://localhost:6379/15",
        "JWT_SECRET": "test_jwt_secret_with_minimum_32_bytes",
        "COOKIE_SECRET": "test_cookie_secret_with_minimum_32_bytes",
    }
    values.update(overrides)
    return Settings(**values)


def test_bitrix24_split_webhook_configuration_is_supported() -> None:
    settings = make_settings(
        BITRIX24_ENABLED=True,
        BITRIX24_BASE_URL="https://bitrix.example.test/rest/1",
        BITRIX24_WEBHOOK_TOKEN="test-token",
    )

    assert settings.bitrix24_base_url == "https://bitrix.example.test/rest/1"
    assert settings.bitrix24_webhook_token == "test-token"


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


def test_invite_email_contains_portal_styled_html_and_inline_logo(tmp_path) -> None:
    logo_path = tmp_path / "ibb-logo.png"
    logo_path.write_bytes(b"fake-png-bytes")

    message = build_invite_email_message(
        to_email="recipient@example.invalid",
        invite_link="https://portal.example.invalid/invite?token=test-token",
        temporary_password="temporary-password",
        from_email="sender@example.invalid",
        logo_path=logo_path,
    )

    assert message["Subject"] == "Приглашение в IBB Insurance Portal"
    assert "temporary-password" in message.get_body(preferencelist=("plain",)).get_content()

    html_body = message.get_body(preferencelist=("html",))
    assert html_body is not None
    html_content = html_body.get_content()
    assert "Добро пожаловать в IBB Insurance Portal" in html_content
    assert "background:#0057a8" in html_content
    assert "cid:" in html_content

    related_logo = next(
        part
        for part in message.walk()
        if part.get_content_maintype() == "image" and part.get_filename() == "ibb-logo.png"
    )
    assert related_logo.get_content_type() == "image/png"


def test_invite_email_uses_requested_language_copy(tmp_path) -> None:
    logo_path = tmp_path / "ibb-logo.png"
    logo_path.write_bytes(b"fake-png-bytes")

    message = build_invite_email_message(
        to_email="recipient@example.invalid",
        invite_link="https://portal.example.invalid/invite?token=test-token",
        temporary_password="temporary-password",
        from_email="sender@example.invalid",
        language="ka",
        logo_path=logo_path,
    )

    assert message["Subject"] == "მოწვევა IBB Insurance Portal-ში"
    html_content = message.get_body(preferencelist=("html",)).get_content()
    assert "პორტალში შესვლა" in html_content
    assert 'dir="ltr"' in html_content


def test_invite_email_sets_rtl_direction_for_rtl_language(tmp_path) -> None:
    logo_path = tmp_path / "ibb-logo.png"
    logo_path.write_bytes(b"fake-png-bytes")

    message = build_invite_email_message(
        to_email="recipient@example.invalid",
        invite_link="https://portal.example.invalid/invite?token=test-token",
        temporary_password="temporary-password",
        from_email="sender@example.invalid",
        language="ar",
        logo_path=logo_path,
    )

    html_content = message.get_body(preferencelist=("html",)).get_content()
    assert 'dir="rtl"' in html_content
