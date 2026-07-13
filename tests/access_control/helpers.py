from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.auth import hash_password
from app.models import (
    document_transfer_logs,
    partner_client_links,
    partner_client_requests,
    portal_applications,
    portal_policies,
    portal_users,
    user_company_roles,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key: str, _ttl: int) -> None:
        self.values.setdefault(key, 0)

    async def get(self, key: str) -> str | None:
        value = self.values.get(key)
        return str(value) if value is not None else None

    async def aclose(self) -> None:
        return None


def create_client(monkeypatch, migrated_database: str) -> TestClient:
    from app.config import get_settings
    from app.main import create_app

    async def redis_factory() -> FakeRedis:
        return FakeRedis()

    import app.auth as auth_module

    monkeypatch.setattr(auth_module, "get_redis_client", redis_factory)
    get_settings.cache_clear()
    return TestClient(create_app())


def login(client: TestClient, email: str, password: str = "StrongPass123!") -> None:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text


def create_request() -> Request:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/access-control/matrix",
            "headers": [
                (b"user-agent", b"pytest"),
                (b"authorization", b"Bearer secret-token-value"),
                (b"cookie", b"session=secret-cookie-value"),
            ],
            "client": ("127.0.0.1", 12345),
        }
    )
    request.state.request_id = "req_access_matrix"
    return request


def create_user(
    session: Session,
    *,
    email: str,
    role_code: str | None = "client_executor",
    user_type: str = "client",
    status: str = "active",
    password: str = "StrongPass123!",
    bitrix_contact_id: int = 7500,
) -> int:
    return session.execute(
        insert(portal_users)
        .values(
            email=email,
            phone="+995555000111",
            password_hash=hash_password(password),
            status=status,
            user_type=user_type,
            role_code=role_code,
            language="ru",
            bitrix_contact_id=bitrix_contact_id,
        )
        .returning(portal_users.c.id)
    ).scalar_one()


def add_company_role(
    session: Session,
    *,
    user_id: int,
    bitrix_company_id: int,
    role_code: str = "client_executor",
    access_status: str = "active",
    company_title_cache: str | None = None,
) -> int:
    return session.execute(
        insert(user_company_roles)
        .values(
            user_id=user_id,
            bitrix_company_id=bitrix_company_id,
            role_code=role_code,
            access_status=access_status,
            bitrix_link_status="confirmed",
            company_title_cache=company_title_cache or f"Company {bitrix_company_id}",
            company_country_code_cache="GE",
            portal_applications_allowed_cache=True,
            auto_ergo_lv_allowed_cache=True,
            auto_dionis_allowed_cache=True,
            auto_deda_allowed_cache=True,
            auto_russian_insurers_allowed_cache=True,
            auto_belarusian_insurers_allowed_cache=True,
            auto_polish_insurers_allowed_cache=True,
            cargo_dionis_allowed_cache=True,
            cargo_deda_allowed_cache=True,
            cargo_russian_insurers_allowed_cache=True,
            cargo_belarusian_insurers_allowed_cache=True,
            cargo_polish_insurers_allowed_cache=True,
        )
        .returning(user_company_roles.c.id)
    ).scalar_one()


def add_partner_link(
    session: Session,
    *,
    partner_user_id: int,
    bitrix_company_id: int,
    status: str = "active",
) -> int:
    return session.execute(
        insert(partner_client_links)
        .values(
            partner_user_id=partner_user_id,
            bitrix_company_id=bitrix_company_id,
            status=status,
            access_status="active" if status in {"active", "another_partner"} else status,
            is_other_partner_client=status == "another_partner",
        )
        .returning(partner_client_links.c.id)
    ).scalar_one()


def add_partner_client_request(
    session: Session,
    *,
    partner_user_id: int,
    status: str = "pending",
    confirmed_bitrix_company_id: int | None = None,
) -> int:
    return session.execute(
        insert(partner_client_requests)
        .values(
            partner_user_id=partner_user_id,
            created_by_user_id=partner_user_id,
            company_name=f"Partner client {partner_user_id}-{status}",
            country="GE",
            registration_number=f"REG-{partner_user_id}-{status}",
            contact_name="Contact",
            contact_email=f"contact-{partner_user_id}-{status}@example.com",
            status=status,
            bitrix_check_status=status if status != "another_partner" else "duplicate_found",
            bitrix_sync_status="synced",
            confirmed_bitrix_company_id=confirmed_bitrix_company_id,
        )
        .returning(partner_client_requests.c.id)
    ).scalar_one()


def add_application(
    session: Session,
    *,
    bitrix_company_id: int,
    bitrix_deal_id: int | None = None,
    created_by_user_id: int | None = None,
    partner_user_id: int | None = None,
    partner_client_request_id: int | None = None,
    portal_status: str = "draft",
    application_type: str = "auto",
    is_hidden_from_partner: bool = False,
    draft_data_json: dict[str, Any] | None = None,
) -> int:
    return session.execute(
        insert(portal_applications)
        .values(
            application_type=application_type,
            bitrix_deal_id=bitrix_deal_id,
            bitrix_company_id=bitrix_company_id,
            bitrix_contact_id=7500,
            portal_status=portal_status,
            bitrix_category_id=0,
            bitrix_stage_id="NEW",
            product_type_code="auto",
            title_cache=f"Application {bitrix_company_id}",
            client_reference_number=f"REF-{bitrix_company_id}",
            draft_data_json=draft_data_json or {},
            created_by_user_id=created_by_user_id,
            partner_user_id=partner_user_id,
            partner_client_request_id=partner_client_request_id,
            is_hidden_from_partner=is_hidden_from_partner,
        )
        .returning(portal_applications.c.id)
    ).scalar_one()


def add_document(
    session: Session,
    *,
    application_id: int,
    bitrix_document_id: str = "B24-DOC-1",
    is_policy_file: bool = False,
    transfer_status: str = "uploaded",
    storage_key: str | None = None,
) -> int:
    return session.execute(
        insert(document_transfer_logs)
        .values(
            application_id=application_id,
            bitrix_document_id=bitrix_document_id,
            bitrix_file_id="B24-FILE-SECRET" if is_policy_file else None,
            document_type="policy_file" if is_policy_file else "client_document",
            is_policy_file=is_policy_file,
            transfer_status=transfer_status,
            storage_key=storage_key,
            mime_type="application/pdf",
            size_bytes=128,
            file_size=128,
        )
        .returning(document_transfer_logs.c.id)
    ).scalar_one()


def add_policy(
    session: Session,
    *,
    application_id: int,
    bitrix_company_id: int,
    bitrix_deal_id: int | None,
    policy_number: str,
    document_transfer_log_id: int | None = None,
    premium_amount: Decimal | None = Decimal("1200.50"),
) -> int:
    return session.execute(
        insert(portal_policies)
        .values(
            application_id=application_id,
            bitrix_deal_id=bitrix_deal_id,
            bitrix_company_id=bitrix_company_id,
            policy_number=policy_number,
            product_type_code="auto",
            insurer_name="Insurer",
            valid_from=date.today() - timedelta(days=10),
            valid_to=date.today() + timedelta(days=90),
            premium_amount=premium_amount,
            premium_currency="USD" if premium_amount is not None else None,
            policy_status="active",
            document_transfer_log_id=document_transfer_log_id,
        )
        .returning(portal_policies.c.id)
    ).scalar_one()


def user_row(session: Session, user_id: int):
    return session.execute(select(portal_users).where(portal_users.c.id == user_id)).mappings().one()


def engine_session(database_url: str):
    return create_engine(database_url)
