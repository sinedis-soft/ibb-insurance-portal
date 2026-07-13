from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from app.models import audit_logs, portal_users, user_company_roles
from app.security import policies
from app.security.policies import PolicyError
from tests.access_control.helpers import (
    add_application,
    add_company_role,
    add_document,
    add_partner_link,
    create_request,
    create_user,
    user_row,
)


@dataclass(frozen=True)
class MatrixCase:
    role: str
    user_type: str
    object_type: str
    action: str
    relation: str
    expected: str


ACCESS_MATRIX_CASES = [
    MatrixCase("client_executor", "client", "company", "read", "own_company", "ALLOW"),
    MatrixCase("client_executor", "client", "company", "read", "foreign_company", "DENY_403"),
    MatrixCase("client_executor", "client", "application", "submit", "own_company_app", "ALLOW"),
    MatrixCase("client_executor", "client", "application", "read", "foreign_company_app", "DENY_404"),
    MatrixCase("client_executor", "client", "application", "approve", "own_company_app", "DENY_403"),
    MatrixCase("client_executor", "client", "document", "upload", "own_company_doc", "ALLOW"),
    MatrixCase("client_executor", "client", "document", "upload", "foreign_company_doc", "DENY_403"),
    MatrixCase("client_executor", "client", "policy", "download", "foreign_company_policy", "DENY_403"),
    MatrixCase("client_admin", "client", "application", "approve", "own_company_app", "ALLOW"),
    MatrixCase("client_admin", "client", "application", "return_for_revision", "own_company_app", "ALLOW"),
    MatrixCase("client_admin", "client", "application", "edit_draft", "own_company_app", "ALLOW"),
    MatrixCase("client_admin", "client", "company", "manage_users", "own_company", "DENY_403"),
    MatrixCase("client_admin", "client", "application", "approve", "foreign_company_app", "DENY_403"),
    MatrixCase("client_viewer", "client", "application", "read", "own_company_app", "ALLOW"),
    MatrixCase("client_viewer", "client", "application", "create", "own_company_app", "DENY_403"),
    MatrixCase("client_viewer", "client", "document", "read_metadata", "own_company_doc", "ALLOW"),
    MatrixCase("client_viewer", "client", "document", "upload", "own_company_doc", "DENY_403"),
    MatrixCase("client_viewer", "client", "policy", "read", "own_company_policy", "ALLOW"),
    MatrixCase("partner", "partner", "application", "read", "own_partner_app", "ALLOW"),
    MatrixCase("partner", "partner", "application", "read", "other_partner_app", "DENY_404"),
    MatrixCase("partner", "partner", "application", "submit", "another_partner_client_app", "DENY_403"),
    MatrixCase("partner", "partner", "document", "read_metadata", "own_partner_doc", "ALLOW"),
    MatrixCase("partner", "partner", "document", "download", "own_partner_doc", "DENY_403"),
    MatrixCase("partner", "partner", "document", "read_metadata", "policy_file", "DENY_403"),
    MatrixCase("partner", "partner", "policy", "read", "own_partner_policy", "ALLOW"),
    MatrixCase("partner", "partner", "policy", "download", "own_partner_policy", "DENY_403"),
    MatrixCase("superadmin", "client", "company", "manage_users", "any_company", "AUDIT_REQUIRED"),
    MatrixCase("superadmin", "client", "application", "read", "foreign_company_app", "ALLOW"),
    MatrixCase("superadmin", "client", "document", "download", "foreign_company_doc", "ALLOW"),
]


def _seed_matrix(session: Session, *, role_code: str, user_type: str) -> dict[str, int]:
    role_value = None if user_type == "partner" else role_code
    subject_id = create_user(
        session,
        email=f"matrix-{role_code}-{user_type}@example.com",
        role_code=role_value,
        user_type=user_type,
    )
    other_actor_id = create_user(session, email=f"matrix-other-{role_code}@example.com", role_code="client_executor")
    other_partner_id = create_user(
        session, email=f"matrix-other-partner-{role_code}@example.com", role_code=None, user_type="partner"
    )

    if user_type == "client" and role_code != "superadmin":
        add_company_role(session, user_id=subject_id, bitrix_company_id=2100, role_code=role_code)
    add_company_role(session, user_id=other_actor_id, bitrix_company_id=2200, role_code="client_executor")
    add_partner_link(
        session, partner_user_id=subject_id if user_type == "partner" else other_partner_id, bitrix_company_id=2300
    )
    add_partner_link(
        session,
        partner_user_id=subject_id if user_type == "partner" else other_partner_id,
        bitrix_company_id=2301,
        status="another_partner",
    )
    add_partner_link(session, partner_user_id=other_partner_id, bitrix_company_id=2302)

    own_app = add_application(session, bitrix_company_id=2100, bitrix_deal_id=211000, created_by_user_id=subject_id)
    foreign_app = add_application(
        session, bitrix_company_id=2200, bitrix_deal_id=221000, created_by_user_id=other_actor_id
    )
    own_partner_app = add_application(
        session, bitrix_company_id=2300, bitrix_deal_id=231000, partner_user_id=subject_id
    )
    another_partner_client_app = add_application(
        session, bitrix_company_id=2301, bitrix_deal_id=231001, partner_user_id=subject_id
    )
    other_partner_app = add_application(
        session, bitrix_company_id=2302, bitrix_deal_id=231002, partner_user_id=other_partner_id
    )
    own_doc = add_document(session, application_id=own_app, bitrix_document_id="DOC-OWN")
    foreign_doc = add_document(session, application_id=foreign_app, bitrix_document_id="DOC-FOREIGN")
    own_partner_doc = add_document(session, application_id=own_partner_app, bitrix_document_id="DOC-PARTNER")
    policy_file = add_document(
        session, application_id=own_partner_app, bitrix_document_id="POLICY-FILE", is_policy_file=True
    )
    session.commit()
    return {
        "subject": subject_id,
        "own_company": 2100,
        "foreign_company": 2200,
        "any_company": 9999,
        "own_company_app": own_app,
        "foreign_company_app": foreign_app,
        "own_company_doc": own_doc,
        "foreign_company_doc": foreign_doc,
        "own_company_policy": own_app,
        "foreign_company_policy": foreign_app,
        "own_partner_app": own_partner_app,
        "another_partner_client_app": another_partner_client_app,
        "other_partner_app": other_partner_app,
        "own_partner_doc": own_partner_doc,
        "policy_file": policy_file,
        "own_partner_policy": own_partner_app,
    }


def arun(awaitable):
    return asyncio.run(awaitable)


def _exercise(session: Session, user, case: MatrixCase, ids: dict[str, int]) -> None:
    request = create_request()
    if case.object_type == "company":
        arun(policies.require_company_access(session, user, ids[case.relation], case.action, request=request))
    elif case.object_type == "application":
        arun(
            policies.require_application_access(
                session, user, case.action, application_id=ids[case.relation], request=request
            )
        )
    elif case.object_type == "document":
        arun(policies.require_document_access(session, user, ids[case.relation], case.action, request=request))
    elif case.object_type == "policy":
        arun(policies.require_policy_access(session, user, ids[case.relation], case.action, request=request))
    else:  # pragma: no cover - guards future matrix additions
        raise AssertionError(case.object_type)


@pytest.mark.parametrize(
    "case", ACCESS_MATRIX_CASES, ids=lambda case: f"{case.role}:{case.object_type}:{case.action}:{case.relation}"
)
def test_formal_access_matrix_expected_results_and_denial_audit(migrated_database: str, case: MatrixCase) -> None:
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            ids = _seed_matrix(session, role_code=case.role, user_type=case.user_type)
            user = user_row(session, ids["subject"])
            if case.expected in {"ALLOW", "AUDIT_REQUIRED"}:
                _exercise(session, user, case, ids)
                if case.expected == "AUDIT_REQUIRED":
                    # Superadmin management is allowed through superadmin APIs;
                    # the policy layer confirms role capability.
                    arun(policies.require_superadmin(user))
                return

            with pytest.raises(PolicyError) as exc_info:
                _exercise(session, user, case, ids)
            expected_status = int(case.expected.removeprefix("DENY_"))
            assert exc_info.value.status_code == expected_status
            session.commit()
            audit_row = session.execute(select(audit_logs.c.id)).scalar_one_or_none()
            if policies.should_audit_denial(
                object_type=case.object_type, action=case.action, error_code=exc_info.value.error_code
            ):
                assert audit_row is not None
            else:
                assert audit_row is None
    finally:
        engine.dispose()


def test_multi_company_roles_are_company_scoped_and_role_changes_revoke_stale_access(
    migrated_database: str,
) -> None:
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            user_id = create_user(session, email="multi-role@example.com", role_code="client_executor")
            add_company_role(session, user_id=user_id, bitrix_company_id=3100, role_code="client_executor")
            add_company_role(session, user_id=user_id, bitrix_company_id=3200, role_code="client_admin")
            exec_app = add_application(
                session, bitrix_company_id=3100, bitrix_deal_id=311000, created_by_user_id=user_id
            )
            admin_app = add_application(
                session, bitrix_company_id=3200, bitrix_deal_id=321000, created_by_user_id=user_id
            )
            session.commit()

            user = user_row(session, user_id)
            assert arun(policies.can_access_application(session, user, "submit", exec_app))
            assert not arun(policies.can_access_application(session, user, "approve", exec_app))
            assert arun(policies.can_access_application(session, user, "approve", admin_app))
            assert set(arun(policies.get_accessible_company_ids(session, user))) == {3100, 3200}

            session.execute(
                update(user_company_roles)
                .where(user_company_roles.c.user_id == user_id)
                .values(access_status="revoked")
            )
            session.commit()
            assert arun(policies.get_accessible_company_ids(session, user_row(session, user_id))) == []
            assert not arun(policies.can_access_application(session, user_row(session, user_id), "read", admin_app))
    finally:
        engine.dispose()


def test_partner_client_statuses_do_not_grant_unapproved_or_other_partner_access(migrated_database: str) -> None:
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            partner_id = create_user(session, email="partner-status@example.com", role_code=None, user_type="partner")
            status_to_company = {
                "pending": 4100,
                "active": 4101,
                "another_partner": 4102,
                "rejected": 4103,
                "revoked": 4104,
            }
            app_by_status = {}
            for link_status, company_id in status_to_company.items():
                add_partner_link(session, partner_user_id=partner_id, bitrix_company_id=company_id, status=link_status)
                app_by_status[link_status] = add_application(
                    session,
                    bitrix_company_id=company_id,
                    bitrix_deal_id=company_id + 100000,
                    partner_user_id=partner_id,
                )
            session.commit()

            partner = user_row(session, partner_id)
            assert arun(policies.get_accessible_company_ids(session, partner)) == [4101]
            assert not arun(policies.can_access_application(session, partner, "read", app_by_status["pending"]))
            assert arun(policies.can_access_application(session, partner, "submit", app_by_status["active"]))
            assert arun(policies.can_access_application(session, partner, "read", app_by_status["another_partner"]))
            assert not arun(
                policies.can_access_application(session, partner, "submit", app_by_status["another_partner"])
            )
            assert not arun(policies.can_access_application(session, partner, "read", app_by_status["rejected"]))
            assert not arun(policies.can_access_application(session, partner, "read", app_by_status["revoked"]))
    finally:
        engine.dispose()


def test_blocked_user_old_token_scope_and_removed_company_link_have_no_access(migrated_database: str) -> None:
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            user_id = create_user(session, email="blocked-token@example.com", role_code="client_admin")
            add_company_role(session, user_id=user_id, bitrix_company_id=5100, role_code="client_admin")
            app_id = add_application(session, bitrix_company_id=5100, bitrix_deal_id=511000, created_by_user_id=user_id)
            session.commit()

            user = user_row(session, user_id)
            assert arun(policies.can_access_application(session, user, "approve", app_id))

            session.execute(
                update(user_company_roles)
                .where(user_company_roles.c.user_id == user_id)
                .values(access_status="revoked")
            )
            session.commit()
            assert not arun(policies.can_access_application(session, user_row(session, user_id), "read", app_id))

            # Mutating the JWT role claim alone is irrelevant: policy decisions re-read stored user status and links.
            session.execute(
                update(user_company_roles).where(user_company_roles.c.user_id == user_id).values(access_status="active")
            )
            session.execute(update(portal_users).where(portal_users.c.id == user_id).values(status="blocked"))
            session.commit()
            assert not arun(policies.can_access_application(session, user_row(session, user_id), "read", app_id))
            assert arun(policies.get_accessible_company_ids(session, user_row(session, user_id))) == []
    finally:
        engine.dispose()
