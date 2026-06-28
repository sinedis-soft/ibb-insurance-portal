from __future__ import annotations

from app.i18n import normalize_locale, section, t
from app.scripts.check_i18n import main as check_backend_i18n


def test_backend_i18n_returns_ru_and_ka_messages() -> None:
    assert t("ru", "errors.SESSION_EXPIRED") == "Сессия истекла"
    assert t("ka", "errors.SESSION_EXPIRED") == "სესიის ვადა ამოიწურა"


def test_backend_i18n_fallback_and_locale_policy() -> None:
    assert normalize_locale("ge") == "ru"
    assert normalize_locale("kz") == "ru"
    assert normalize_locale("ka-GE") == "ka"
    assert normalize_locale("en") == "ru"
    assert t("en", "errors.USER_BLOCKED") == "Пользователь заблокирован"


def test_backend_i18n_email_and_status_sections() -> None:
    assert section("ru", "email.invite")["subject"] == "Приглашение в IBB Insurance Portal"
    assert section("ka", "email.invite")["button"] == "პორტალში შესვლა"
    assert t("ru", "statuses.policy_issued") == "Полис выпущен"
    assert t("ka", "statuses.policy_issued") == "პოლისი გამოშვებულია"


def test_backend_hardcoded_i18n_check_passes() -> None:
    assert check_backend_i18n() == 0
