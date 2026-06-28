from __future__ import annotations

import logging

import pytest
from sqlalchemy import create_engine, insert, select, update
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.auth import hash_password
from app.models import (
    audit_logs,
    document_transfer_logs,
    partner_client_links,
    portal_applications,
    portal_users,
    user_company_roles,
)
from app.security import policies
from app.security.policies import PolicyError


class ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def create_request() -> Request:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/applications/999",
            "headers": [(b"user-agent", b"pytest")],
            "client": ("127.0.0.1", 12345),
        }
    )
    request.state.request_id = "req_policy_test"
    return request


def create_user(
    session: Session,
    *,
    email: str,
    role_code: str | None = "client_executor",
    user_type: str = "client",
    status: str = "active",
) -> int:
    return session.execute(
        insert(portal_users)
        .values(
            email=email,
            password_hash=hash_password("StrongPass123!"),
            status=status,
            user_type=user_type,
            role_code=role_code,
            language="ru",
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
) -> int:
    return session.execute(
        insert(user_company_roles)
        .values(
            user_id=user_id,
            bitrix_company_id=bitrix_company_id,
            role_code=role_code,
            access_status=access_status,
            bitrix_link_status="confirmed",
        )
        .returning(user_company_roles.c.id)
    ).scalar_one()


def add_application(
    session: Session,
    *,
    bitrix_company_id: int,
    bitrix_deal_id: int,
    created_by_user_id: int | None = None,
    partner_user_id: int | None = None,
    is_hidden_from_partner: bool = False,
) -> int:
    return session.execute(
        insert(portal_applications)
        .values(
            bitrix_company_id=bitrix_company_id,
            bitrix_deal_id=bitrix_deal_id,
            portal_status="draft",
            created_by_user_id=created_by_user_id,
            partner_user_id=partner_user_id,
            is_hidden_from_partner=is_hidden_from_partner,
        )
        .returning(portal_applications.c.id)
    ).scalar_one()


def add_document(
    session: Session,
    *,
    application_id: int,
    is_policy_file: bool = False,
    document_type: str = "client_document",
) -> int:
    return session.execute(
        insert(document_transfer_logs)
        .values(
            application_id=application_id,
            document_type=document_type,
            is_policy_file=is_policy_file,
            transfer_status="pending",
        )
        .returning(document_transfer_logs.c.id)
    ).scalar_one()


def user_row(session: Session, user_id: int):
    return session.execute(select(portal_users).where(portal_users.c.id == user_id)).mappings().one()


@pytest.mark.asyncio
async def test_company_policy_active_revoked_pending_blocked_and_superadmin(migrated_database: str) -> None:
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            active = create_user(session, email="active@example.com")
            revoked = create_user(session, email="revoked@example.com")
            pending = create_user(session, email="pending@example.com")
            blocked = create_user(session, email="blocked@example.com", status="blocked")
            admin = create_user(session, email="admin@example.com", role_code="superadmin")
            add_company_role(session, user_id=active, bitrix_company_id=100)
            add_company_role(session, user_id=revoked, bitrix_company_id=100, access_status="revoked")
            add_company_role(session, user_id=pending, bitrix_company_id=100, access_status="pending")
            session.commit()

            assert await policies.can_access_company(session, user_row(session, active), 100, "read")
            assert not await policies.can_access_company(session, user_row(session, revoked), 100, "read")
            assert not await policies.can_access_company(session, user_row(session, pending), 100, "read")
            assert not await policies.can_access_company(session, user_row(session, blocked), 100, "read")
            assert await policies.can_access_company(session, user_row(session, admin), 999, "approve_application")
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_application_policy_roles_guessed_ids_and_revoked_access(migrated_database: str) -> None:
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            executor = create_user(session, email="executor@example.com", role_code="client_executor")
            viewer = create_user(session, email="viewer@example.com", role_code="client_viewer")
            admin = create_user(session, email="client-admin@example.com", role_code="client_admin")
            stranger = create_user(session, email="stranger@example.com", role_code="client_executor")
            revoked = create_user(session, email="revoked@example.com", role_code="client_executor")
            add_company_role(session, user_id=executor, bitrix_company_id=200, role_code="client_executor")
            add_company_role(session, user_id=viewer, bitrix_company_id=200, role_code="client_viewer")
            add_company_role(session, user_id=admin, bitrix_company_id=200, role_code="client_admin")
            add_company_role(session, user_id=stranger, bitrix_company_id=201, role_code="client_executor")
            add_company_role(
                session,
                user_id=revoked,
                bitrix_company_id=200,
                role_code="client_executor",
                access_status="revoked",
            )
            app_id = add_application(session, bitrix_company_id=200, bitrix_deal_id=88001, created_by_user_id=executor)
            session.commit()

            assert (await policies.require_application_access(session, user_row(session, executor), "read", app_id)).id
            assert await policies.can_access_application(session, user_row(session, executor), "submit", app_id)
            assert not await policies.can_access_application(session, user_row(session, viewer), "submit", app_id)
            assert await policies.can_access_application(session, user_row(session, admin), "approve", app_id)
            assert not await policies.can_access_application(session, user_row(session, stranger), "read", app_id)
            assert not await policies.can_access_application(
                session,
                user_row(session, stranger),
                "read",
                bitrix_deal_id=88001,
            )
            assert not await policies.can_access_application(session, user_row(session, revoked), "read", app_id)

            with pytest.raises(PolicyError) as exc_info:
                await policies.require_application_access(session, user_row(session, stranger), "read", app_id)
            assert exc_info.value.status_code == 404
            assert exc_info.value.error_code == "APPLICATION_ACCESS_DENIED"
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_partner_policy_is_limited_to_own_application_and_no_policy_file(
    migrated_database: str,
) -> None:
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            partner = create_user(session, email="partner@example.com", role_code=None, user_type="partner")
            other_partner = create_user(session, email="other-partner@example.com", role_code=None, user_type="partner")
            client = create_user(session, email="client@example.com")
            session.execute(
                insert(partner_client_links).values(
                    partner_user_id=partner,
                    client_user_id=client,
                    bitrix_company_id=300,
                    access_status="active",
                )
            )
            own_app = add_application(session, bitrix_company_id=300, bitrix_deal_id=99001, partner_user_id=partner)
            other_app = add_application(
                session,
                bitrix_company_id=300,
                bitrix_deal_id=99002,
                partner_user_id=other_partner,
            )
            policy_document = add_document(
                session,
                application_id=own_app,
                is_policy_file=True,
                document_type="policy_file",
            )
            session.commit()

            assert await policies.can_access_application(session, user_row(session, partner), "read", own_app)
            assert not await policies.can_access_application(session, user_row(session, partner), "read", other_app)
            assert not await policies.can_access_policy(session, user_row(session, partner), own_app, "download")
            assert not await policies.can_access_document(
                session,
                user_row(session, partner),
                policy_document,
                "download",
            )
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_document_and_policy_policy_client_negative_cases_are_audited_and_sanitized(
    migrated_database: str,
) -> None:
    engine = create_engine(migrated_database)
    handler = ListHandler()
    logger = logging.getLogger("ibb_portal")
    logger.disabled = False
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        with Session(engine) as session:
            owner = create_user(session, email="owner@example.com", role_code="client_executor")
            viewer = create_user(session, email="viewer@example.com", role_code="client_viewer")
            stranger = create_user(session, email="stranger@example.com", role_code="client_executor")
            add_company_role(session, user_id=owner, bitrix_company_id=400, role_code="client_executor")
            add_company_role(session, user_id=viewer, bitrix_company_id=400, role_code="client_viewer")
            add_company_role(session, user_id=stranger, bitrix_company_id=401, role_code="client_executor")
            app_id = add_application(session, bitrix_company_id=400, bitrix_deal_id=77001, created_by_user_id=owner)
            doc_id = add_document(session, application_id=app_id)
            session.commit()

            assert await policies.can_access_document(session, user_row(session, owner), doc_id, "upload")
            assert not await policies.can_access_document(session, user_row(session, stranger), doc_id, "read_metadata")
            assert not await policies.can_access_policy(session, user_row(session, viewer), app_id, "request_send")

            request = create_request()
            with pytest.raises(PolicyError):
                await policies.require_document_access(
                    session,
                    user_row(session, stranger),
                    doc_id,
                    "read_metadata",
                    request=request,
                )
            session.commit()

            audit_row = session.execute(
                select(audit_logs).where(audit_logs.c.action == "document_access_denied")
            ).mappings().one()
            assert audit_row.metadata_json["reason_code"] == "DOCUMENT_ACCESS_DENIED"
            assert audit_row.metadata_json["action"] == "read_metadata"
            assert "owner@example.com" not in str(audit_row.metadata_json)
            assert "SensitiveFile.pdf" not in str(audit_row.metadata_json)
    finally:
        logger.removeHandler(handler)
        engine.dispose()

    log_text = "\n".join(handler.messages)
    assert "access_denied" in log_text
    assert "owner@example.com" not in log_text
    assert "stranger@example.com" not in log_text
    assert "+995" not in log_text
    assert "SensitiveFile.pdf" not in log_text
    assert "request body" not in log_text


@pytest.mark.asyncio
async def test_accessible_application_filter_returns_only_allowed_records(migrated_database: str) -> None:
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            user = create_user(session, email="user@example.com", role_code="client_executor")
            add_company_role(session, user_id=user, bitrix_company_id=500)
            allowed = add_application(session, bitrix_company_id=500, bitrix_deal_id=55001)
            denied = add_application(session, bitrix_company_id=501, bitrix_deal_id=55002)
            session.commit()

            accessible = await policies.get_accessible_application_filter(session, user_row(session, user))

            assert allowed in accessible
            assert denied not in accessible

            session.execute(
                update(user_company_roles)
                .where(user_company_roles.c.user_id == user)
                .values(access_status="revoked")
            )
            session.commit()
            assert await policies.get_accessible_application_filter(session, user_row(session, user)) == []
    finally:
        engine.dispose()
