from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import user_company_roles
from app.security.policies import is_superadmin


@dataclass(frozen=True, slots=True)
class CompanyEligibility:
    portal_applications_allowed: bool
    auto: dict[str, bool]
    cargo: dict[str, bool]


AUTO_ERROR_CODES = {
    "ergo_lv": "AUTO_ERGO_LV_NOT_ALLOWED",
    "dionis": "AUTO_DIONIS_NOT_ALLOWED",
    "deda": "AUTO_DEDA_NOT_ALLOWED",
    "russian_insurers": "AUTO_RUSSIAN_INSURERS_NOT_ALLOWED",
    "belarusian_insurers": "AUTO_BELARUSIAN_INSURERS_NOT_ALLOWED",
    "polish_insurers": "AUTO_POLISH_INSURERS_NOT_ALLOWED",
}

CARGO_ERROR_CODES = {
    "dionis": "CARGO_DIONIS_NOT_ALLOWED",
    "deda": "CARGO_DEDA_NOT_ALLOWED",
    "russian_insurers": "CARGO_RUSSIAN_INSURERS_NOT_ALLOWED",
    "belarusian_insurers": "CARGO_BELARUSIAN_INSURERS_NOT_ALLOWED",
    "polish_insurers": "CARGO_POLISH_INSURERS_NOT_ALLOWED",
}


def _empty_eligibility() -> CompanyEligibility:
    return CompanyEligibility(
        portal_applications_allowed=False,
        auto={key: False for key in AUTO_ERROR_CODES},
        cargo={key: False for key in CARGO_ERROR_CODES},
    )


def _full_eligibility() -> CompanyEligibility:
    return CompanyEligibility(
        portal_applications_allowed=True,
        auto={key: True for key in AUTO_ERROR_CODES},
        cargo={key: True for key in CARGO_ERROR_CODES},
    )


def company_eligibility(session: Session, user, bitrix_company_id: int) -> CompanyEligibility:
    if is_superadmin(user):
        return _full_eligibility()
    row = (
        session.execute(
            select(user_company_roles).where(
                user_company_roles.c.user_id == user.id,
                user_company_roles.c.bitrix_company_id == bitrix_company_id,
                user_company_roles.c.access_status == "active",
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return _empty_eligibility()
    return CompanyEligibility(
        portal_applications_allowed=bool(row.portal_applications_allowed_cache),
        auto={
            "ergo_lv": bool(row.auto_ergo_lv_allowed_cache),
            "dionis": bool(row.auto_dionis_allowed_cache),
            "deda": bool(row.auto_deda_allowed_cache),
            "russian_insurers": bool(row.auto_russian_insurers_allowed_cache),
            "belarusian_insurers": bool(row.auto_belarusian_insurers_allowed_cache),
            "polish_insurers": bool(row.auto_polish_insurers_allowed_cache),
        },
        cargo={
            "dionis": bool(row.cargo_dionis_allowed_cache),
            "deda": bool(row.cargo_deda_allowed_cache),
            "russian_insurers": bool(row.cargo_russian_insurers_allowed_cache),
            "belarusian_insurers": bool(row.cargo_belarusian_insurers_allowed_cache),
            "polish_insurers": bool(row.cargo_polish_insurers_allowed_cache),
        },
    )


def auto_contour_for_product(
    product_code: str,
    *,
    vehicle_registration_country_code: str | None,
    coverage_country_code: str | None,
    coverage_zone_code: str | None,
) -> str:
    if product_code == "osago_rf" or coverage_country_code == "RU":
        return "russian_insurers"
    if coverage_country_code == "BY":
        return "belarusian_insurers"
    if product_code in {"pl_oc", "pl_ac"} or coverage_country_code == "PL":
        return "polish_insurers"
    if coverage_country_code == "LV":
        return "ergo_lv"
    if coverage_country_code == "GE" or vehicle_registration_country_code == "GE":
        return "deda"
    if coverage_country_code == "KZ" or vehicle_registration_country_code == "KZ":
        return "dionis"
    if coverage_zone_code == "EU":
        return "polish_insurers"
    return "dionis"


def cargo_contour_for_payload(payload: dict) -> str:
    route = payload.get("route") or {}
    countries = {route.get("country_from"), route.get("country_to")}
    if "RU" in countries:
        return "russian_insurers"
    if "BY" in countries:
        return "belarusian_insurers"
    if "PL" in countries:
        return "polish_insurers"
    if "GE" in countries:
        return "deda"
    return "dionis"


def auto_allowed_reason(
    eligibility: CompanyEligibility,
    product_code: str,
    *,
    vehicle_registration_country_code: str | None,
    coverage_country_code: str | None,
    coverage_zone_code: str | None,
) -> str | None:
    if not eligibility.portal_applications_allowed:
        return "PORTAL_APPLICATIONS_NOT_ALLOWED"
    contour = auto_contour_for_product(
        product_code,
        vehicle_registration_country_code=vehicle_registration_country_code,
        coverage_country_code=coverage_country_code,
        coverage_zone_code=coverage_zone_code,
    )
    return None if eligibility.auto.get(contour, False) else AUTO_ERROR_CODES[contour]


def cargo_allowed_reason(eligibility: CompanyEligibility, payload: dict) -> str | None:
    if not eligibility.portal_applications_allowed:
        return "PORTAL_APPLICATIONS_NOT_ALLOWED"
    contour = cargo_contour_for_payload(payload)
    return None if eligibility.cargo.get(contour, False) else CARGO_ERROR_CODES[contour]
