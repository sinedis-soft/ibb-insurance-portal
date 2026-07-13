# Access-control automated test plan

This document records the MVP access-control test scope for the IBB Insurance Portal. The source of truth is the formal matrix in `docs/access-control-matrix.md`; automated coverage must keep Bitrix24 as the system of record and verify that portal-local links, roles, drafts, document-transfer metadata, partner visibility, and audit events cannot expand access.

## Test layers

### Policy layer

`tests/access_control/test_role_permission_matrix.py` verifies the formal role matrix for `client_executor`, `client_admin`, `client_viewer`, `partner`, and `superadmin` against the policy functions in `app/security/policies.py`. These tests cover direct checks for company, application, policy, and document access; cross-company IDOR; partner policy-file denial; inactive links; blocked users; multi-company users; stale access after role/link revocation; and partner-client link statuses.

### HTTP API layer

`tests/access_control/test_endpoint_access_control.py` exercises real FastAPI endpoints through `TestClient` with cookie-based authentication and a migrated test database. It covers:

- `/me/companies` list scoping;
- `/applications` list/detail scoping, pagination-style parameters, foreign `company_id`, and executor own-application restrictions;
- `/auto/applications/draft`, draft update, document upload, and submit with forged body fields;
- `/policies` list/detail scoping, policy number/validity/premium visibility, and foreign policy masking;
- `/applications/{application_id}/documents` metadata scoping;
- `/documents/{document_id}/download` policy-file and foreign-document denial;
- `/partner/clients` list scoping with ignored forged query parameters;
- blocked-user, role-change, and company-link revocation behavior through active HTTP sessions.

### SQL/ORM filtering

The endpoint tests assert response contents, not only status codes. They seed same-company, foreign-company, partner-owned, and other-partner rows and verify that list endpoints never return foreign records even when filters such as `company_id`, search, pagination, `include`, `sort`, `partner_id`, `partner_client_id`, or `application_id` are supplied by the caller.

## Audit and security event model

Business audit log is not a generic 403/404 log. Ordinary masked reads, such as requesting another company's application and receiving `404`, must not create business audit noise.

Audit rows are required for business/security-sensitive events, including:

- administrative action attempts without permission;
- role and company-link changes;
- partner-client link changes;
- user blocking/unblocking;
- application creation/submission and Bitrix24 sync outcomes;
- document upload, protected document download attempts, and document transfer outcomes;
- superadmin impersonation start/end and actions performed during impersonation when that MVP feature is implemented.

Technical access-denied messages remain in sanitized application logs and must not contain request bodies, personal data, document filenames, storage keys, Bitrix24 file IDs, cookies, or tokens.

## CI/CD gate

The dedicated access-control gate command is:

```bash
pytest tests/access_control -q --strict-markers
```

The stable GitHub required status-check name to enable in branch protection is:

```text
Backend checks and access-control gate
```

The workflow also rejects unapproved `skip`, `skipif`, and `xfail` markers in access-control suites, runs backend lint, secret scanning, the full backend suite, backend Docker build, and frontend lint/typecheck/build. The access-control gate uses local database fixtures and fake/mocked external services; it must not depend on production Bitrix24.

## Dependency reproducibility

Backend CI installs `requirements-dev.txt`, which uses `requirements-dev.constraints.txt` for pinned test-tool versions while keeping the package metadata in `pyproject.toml` as the source for application dependencies. This avoids adding a new package manager just for this task.

## MVP boundaries and deferred scope

- Bitrix24 remains the business system of record for companies, contacts, deals, policies, documents, stages, internal comments, and operator work.
- The portal stores only authentication/session state, user-company roles, partner links, drafts, sync/cache metadata, document-transfer metadata, safe user actions, and PostgreSQL business audit events.
- Temporary self-service delegation by an executor is not in MVP.
- Permanent specialist replacement is not in MVP beyond admin block-and-transfer behavior.
- Complex observer permission configuration is not in MVP.
- Client self-creation of confirmed users is not in MVP.
- Downloading client documents from the portal is not in MVP.
- Partner commission calculation and multi-employee partner organizations are not in MVP.
- A partner must not receive a policy file, download URL, Bitrix24 file ID, storage key, signed URL, download token, or any technical identifier that enables file download.

For temporary delegation, tests should only assert that no additional access is granted without an active same-company role or active partner link.

## Known implementation gaps tracked by tests/docs

- Dedicated superadmin impersonation endpoints and an impersonation-session table are not present yet. Current superadmin tests cover management/audit endpoints, and this document records the required impersonation audit semantics for the MVP implementation.
- A global `GET /documents` metadata list endpoint is not present. MVP coverage uses application-scoped document metadata and direct download endpoints; adding a global list later must include the same access-control content assertions.
