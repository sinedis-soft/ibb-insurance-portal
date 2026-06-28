from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient
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
) -> int:
    return session.execute(
        insert(portal_users)
        .values(
            email=email,
            phone="+995555000111",
            password_hash=hash_password("StrongPass123!"),
            status=status,
            user_type=user_type,
            role_code=role_code,
            language="ru",
            bitrix_contact_id=7500,
        )
        .returning(portal_users.c.id)
    ).scalar_one()


def add_company_role(
    session: Session,
    *,
    user_id: int,
    bitrix_company_id: int,
    role_code: str,
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
            company_title_cache="Sensitive Company Title",
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
    bitrix_document_id: str,
    is_policy_file: bool = False,
) -> int:
    return session.execute(
        insert(document_transfer_logs)
        .values(
            application_id=application_id,
            bitrix_document_id=bitrix_document_id,
            document_type="policy_file" if is_policy_file else "client_document",
            is_policy_file=is_policy_file,
            transfer_status="uploaded",
        )
        .returning(document_transfer_logs.c.id)
    ).scalar_one()


def user_row(session: Session, user_id: int):
    return session.execute(select(portal_users).where(portal_users.c.id == user_id)).mappings().one()


def test_unauthenticated_company_list_is_401(migrated_database: str) -> None:
    from app.main import create_app

    with TestClient(create_app()) as client:
        response = client.get("/me/companies")

    assert response.status_code == 401
    assert response.json()["error_code"] == "SESSION_EXPIRED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "role_code",
        "company_action",
        "application_action",
        "policy_action",
        "document_action",
        "company_expected",
        "application_expected",
        "policy_expected",
        "document_expected",
    ),
    [
        ("client_executor", "create_application", "submit", "request_send", "upload", True, True, True, True),
        ("client_admin", "approve_application", "approve", "request_send", "download", True, True, True, True),
        ("client_viewer", "read", "read", "read", "read_metadata", True, True, True, True),
        ("client_viewer", "create_application", "submit", "request_send", "upload", False, False, False, False),
        ("client_executor", "approve_application", "approve", "read", "read_metadata", False, False, True, True),
    ],
)
async def test_client_role_matrix_matches_policy_contract(
    migrated_database: str,
    role_code: str,
    company_action: str,
    application_action: str,
    policy_action: str,
    document_action: str,
    company_expected: bool,
    application_expected: bool,
    policy_expected: bool,
    document_expected: bool,
) -> None:
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            user_id = create_user(session, email=f"{role_code}-{application_action}@example.com", role_code=role_code)
            add_company_role(session, user_id=user_id, bitrix_company_id=1000, role_code=role_code)
            app_id = add_application(session, bitrix_company_id=1000, bitrix_deal_id=101000, created_by_user_id=user_id)
            doc_id = add_document(session, application_id=app_id, bitrix_document_id="DOC-1000")
            session.commit()

            user = user_row(session, user_id)
            assert await policies.can_access_company(session, user, 1000, company_action) is company_expected
            assert (
                await policies.can_access_application(session, user, application_action, app_id)
                is application_expected
            )
            assert await policies.can_access_policy(session, user, app_id, policy_action) is policy_expected
            assert await policies.can_access_document(session, user, doc_id, document_action) is document_expected
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("access_status", ["revoked", "pending", "rejected"])
async def test_inactive_company_role_blocks_company_application_policy_document_and_search(
    migrated_database: str,
    access_status: str,
) -> None:
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            user_id = create_user(session, email=f"{access_status}@example.com", role_code="client_executor")
            add_company_role(
                session,
                user_id=user_id,
                bitrix_company_id=1100,
                role_code="client_executor",
                access_status=access_status,
            )
            app_id = add_application(session, bitrix_company_id=1100, bitrix_deal_id=111000, created_by_user_id=user_id)
            doc_id = add_document(session, application_id=app_id, bitrix_document_id="DOC-1100")
            session.commit()

            user = user_row(session, user_id)
            assert not await policies.can_access_company(session, user, 1100, "read")
            assert not await policies.can_access_application(session, user, "read", app_id)
            assert not await policies.can_access_policy(session, user, app_id, "read")
            assert not await policies.can_access_document(session, user, doc_id, "read_metadata")
            assert await policies.search_accessible_applications(session, user, "111000") == []
            assert await policies.search_accessible_documents(session, user, "DOC-1100") == []
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_blocked_user_and_foreign_guessed_ids_are_denied_and_masked(migrated_database: str) -> None:
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            owner_id = create_user(session, email="owner@example.com", role_code="client_executor")
            stranger_id = create_user(session, email="stranger@example.com", role_code="client_executor")
            blocked_id = create_user(
                session,
                email="blocked@example.com",
                role_code="client_executor",
                status="blocked",
            )
            add_company_role(session, user_id=owner_id, bitrix_company_id=1200, role_code="client_executor")
            add_company_role(session, user_id=stranger_id, bitrix_company_id=1201, role_code="client_executor")
            add_company_role(session, user_id=blocked_id, bitrix_company_id=1200, role_code="client_executor")
            app_id = add_application(
                session,
                bitrix_company_id=1200,
                bitrix_deal_id=121000,
                created_by_user_id=owner_id,
            )
            doc_id = add_document(session, application_id=app_id, bitrix_document_id="DOC-1200")
            session.commit()

            stranger = user_row(session, stranger_id)
            blocked = user_row(session, blocked_id)

            with pytest.raises(PolicyError) as app_exc:
                await policies.require_application_access(session, stranger, "read", application_id=app_id)
            assert app_exc.value.status_code == 404
            assert app_exc.value.error_code == "APPLICATION_ACCESS_DENIED"

            with pytest.raises(PolicyError) as invalid_action_exc:
                await policies.require_application_access(session, user_row(session, owner_id), "delete", app_id)
            assert invalid_action_exc.value.status_code == 403
            assert invalid_action_exc.value.error_code == "APPLICATION_ACCESS_DENIED"

            with pytest.raises(PolicyError) as missing_app_exc:
                await policies.require_application_access(session, stranger, "read", application_id=999999)
            assert missing_app_exc.value.status_code == 404
            assert missing_app_exc.value.error_code == "APPLICATION_NOT_FOUND"

            assert not await policies.can_access_application(session, stranger, "read", bitrix_deal_id=121000)
            assert not await policies.can_access_document(session, stranger, doc_id, "download")
            assert await policies.get_accessible_application_filter(session, blocked) == []
            assert await policies.search_accessible_applications(session, blocked, "121000") == []
            assert await policies.search_accessible_documents(session, blocked, "DOC-1200") == []

            with pytest.raises(PolicyError) as missing_exc:
                await policies.require_document_access(session, stranger, 999999, "download")
            assert missing_exc.value.status_code == 404
            assert missing_exc.value.error_code == "DOCUMENT_NOT_FOUND"
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_partner_client_scope_revoked_another_partner_and_documents(migrated_database: str) -> None:
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            partner_id = create_user(session, email="partner@example.com", role_code=None, user_type="partner")
            other_partner_id = create_user(
                session,
                email="other-partner@example.com",
                role_code=None,
                user_type="partner",
            )
            add_partner_link(session, partner_user_id=partner_id, bitrix_company_id=1300, status="active")
            add_partner_link(session, partner_user_id=partner_id, bitrix_company_id=1301, status="revoked")
            add_partner_link(session, partner_user_id=partner_id, bitrix_company_id=1302, status="another_partner")
            own_app = add_application(
                session,
                bitrix_company_id=1300,
                bitrix_deal_id=131000,
                partner_user_id=partner_id,
            )
            linked_client_other_app = add_application(
                session,
                bitrix_company_id=1300,
                bitrix_deal_id=131001,
                partner_user_id=other_partner_id,
            )
            revoked_app = add_application(
                session,
                bitrix_company_id=1301,
                bitrix_deal_id=131002,
                partner_user_id=partner_id,
            )
            another_partner_app = add_application(
                session,
                bitrix_company_id=1302,
                bitrix_deal_id=131003,
                partner_user_id=partner_id,
            )
            own_doc = add_document(session, application_id=own_app, bitrix_document_id="DOC-1300")
            policy_doc = add_document(
                session,
                application_id=own_app,
                bitrix_document_id="POLICY-1300",
                is_policy_file=True,
            )
            session.commit()

            partner = user_row(session, partner_id)
            partner_apps = await policies.search_accessible_applications(session, partner)
            partner_docs = await policies.search_accessible_documents(session, partner)

            assert [row.id for row in partner_apps] == [own_app, another_partner_app]
            assert [row.id for row in partner_docs] == [own_doc]
            assert await policies.get_accessible_company_ids(session, partner) == [1300]
            assert await policies.can_access_application(session, partner, "read", own_app)
            assert not await policies.can_access_application(session, partner, "read", linked_client_other_app)
            assert not await policies.can_access_application(session, partner, "read", revoked_app)
            assert await policies.can_access_application(session, partner, "read", another_partner_app)
            assert not await policies.can_access_application(session, partner, "submit", another_partner_app)
            assert not await policies.can_access_policy(session, partner, own_app, "download")
            assert not await policies.can_access_document(session, partner, policy_doc, "download")
            assert await policies.search_accessible_applications(session, partner, "131001") == []
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_policy_and_document_denials_are_audited_and_safe_logged(migrated_database: str) -> None:
    engine = create_engine(migrated_database)
    handler = ListHandler()
    logger = logging.getLogger("ibb_portal")
    logger.disabled = False
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        with Session(engine) as session:
            partner_id = create_user(
                session,
                email="partner-sensitive@example.com",
                role_code=None,
                user_type="partner",
            )
            add_partner_link(session, partner_user_id=partner_id, bitrix_company_id=1400, status="active")
            app_id = add_application(session, bitrix_company_id=1400, bitrix_deal_id=141000, partner_user_id=partner_id)
            policy_doc = add_document(
                session,
                application_id=app_id,
                bitrix_document_id="SensitivePolicyFile.pdf",
                is_policy_file=True,
            )
            session.commit()

            request = create_request()
            with pytest.raises(PolicyError):
                await policies.require_document_access(
                    session,
                    user_row(session, partner_id),
                    policy_doc,
                    "download",
                    request=request,
                )
            with pytest.raises(PolicyError):
                await policies.require_policy_access(
                    session,
                    user_row(session, partner_id),
                    app_id,
                    "request_send",
                    request=request,
                )
            session.commit()

            audit_rows = session.execute(select(audit_logs).order_by(audit_logs.c.id)).mappings().all()
            assert [row.action for row in audit_rows] == ["document_access_denied", "policy_access_denied"]
            for row in audit_rows:
                assert row.metadata_json["status"] == "denied"
                assert "partner-sensitive@example.com" not in str(row.metadata_json)
                assert "+995555000111" not in str(row.metadata_json)
                assert "Sensitive Company Title" not in str(row.metadata_json)
                assert "SensitivePolicyFile.pdf" not in str(row.metadata_json)
    finally:
        logger.removeHandler(handler)
        engine.dispose()

    log_text = "\n".join(handler.messages)
    assert "access_denied" in log_text
    assert "partner-sensitive@example.com" not in log_text
    assert "+995555000111" not in log_text
    assert "Sensitive Company Title" not in log_text
    assert "SensitivePolicyFile.pdf" not in log_text
    assert "secret-token-value" not in log_text
    assert "secret-cookie-value" not in log_text
    assert "request body" not in log_text


@pytest.mark.asyncio
async def test_delegation_placeholder_does_not_grant_access_without_active_company_role(
    migrated_database: str,
) -> None:
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            executor_id = create_user(session, email="delegated-executor@example.com", role_code="client_executor")
            viewer_id = create_user(session, email="delegated-viewer@example.com", role_code="client_viewer")
            outsider_id = create_user(session, email="delegated-outsider@example.com", role_code="client_executor")
            blocked_id = create_user(
                session,
                email="delegated-blocked@example.com",
                role_code="client_executor",
                status="blocked",
            )
            add_company_role(session, user_id=executor_id, bitrix_company_id=1500, role_code="client_executor")
            add_company_role(session, user_id=viewer_id, bitrix_company_id=1500, role_code="client_viewer")
            add_company_role(session, user_id=outsider_id, bitrix_company_id=1501, role_code="client_executor")
            add_company_role(session, user_id=blocked_id, bitrix_company_id=1500, role_code="client_executor")
            app_id = add_application(session, bitrix_company_id=1500, bitrix_deal_id=151000)
            own_doc = add_document(session, application_id=app_id, bitrix_document_id="DOC-1500")
            other_app = add_application(session, bitrix_company_id=1501, bitrix_deal_id=151001)
            other_doc = add_document(session, application_id=other_app, bitrix_document_id="DOC-1501")
            session.commit()

            executor = user_row(session, executor_id)
            viewer = user_row(session, viewer_id)
            outsider = user_row(session, outsider_id)
            blocked = user_row(session, blocked_id)

            assert await policies.can_access_application(session, executor, "read", app_id)
            assert await policies.can_access_application(session, executor, "submit", app_id)
            assert await policies.can_access_application(session, viewer, "read", app_id)
            assert not await policies.can_access_application(session, viewer, "submit", app_id)
            assert not await policies.can_access_application(session, outsider, "read", app_id)
            assert not await policies.can_access_application(session, blocked, "read", app_id)
            assert [row.id for row in await policies.search_accessible_documents(session, executor)] == [own_doc]
            assert other_doc not in [row.id for row in await policies.search_accessible_documents(session, executor)]

            session.execute(
                update(user_company_roles)
                .where(user_company_roles.c.user_id == executor_id)
                .values(access_status="revoked")
            )
            session.commit()
            assert not await policies.can_access_application(session, user_row(session, executor_id), "read", app_id)
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_superadmin_matrix_can_inspect_everything_but_role_management_still_requires_superadmin(
    migrated_database: str,
) -> None:
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            admin_id = create_user(session, email="matrix-admin@example.com", role_code="superadmin")
            client_admin_id = create_user(session, email="matrix-client-admin@example.com", role_code="client_admin")
            add_company_role(session, user_id=client_admin_id, bitrix_company_id=1600, role_code="client_admin")
            app_id = add_application(session, bitrix_company_id=1600, bitrix_deal_id=161000)
            doc_id = add_document(session, application_id=app_id, bitrix_document_id="DOC-1600")
            session.commit()

            admin = user_row(session, admin_id)
            client_admin = user_row(session, client_admin_id)

            assert await policies.can_access_company(session, admin, 999999, "manage_users")
            assert await policies.can_access_application(session, admin, "approve", app_id)
            assert await policies.can_access_policy(session, admin, app_id, "download")
            assert await policies.can_access_document(session, admin, doc_id, "download")
            await policies.require_superadmin(admin)
            with pytest.raises(PolicyError) as exc_info:
                await policies.require_superadmin(client_admin)
            assert exc_info.value.status_code == 403
            assert exc_info.value.error_code == "SUPERADMIN_REQUIRED"
    finally:
        engine.dispose()
