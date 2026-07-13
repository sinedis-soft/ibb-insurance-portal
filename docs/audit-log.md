# Business audit log

IBB Portal keeps a PostgreSQL business audit log for critical security and access-control actions. Technical logs remain separate and are used only for operational debugging.

## Categories

The superadmin audit view exposes these normalized categories:

- `authentication` — login, logout, session revocation, password and token lifecycle, 2FA checks.
- `access_control` — sensitive policy denials and company/application/document access failures.
- `user_management` — user creation, role changes, company links, blocking, unblocking, Bitrix24 technical links.
- `application` — application creation/submission/status and reassignment facts.
- `document` — document upload, safe transfer status, retry and protected download denials.
- `delegation` — temporary delegation lifecycle and delegated application actions.
- `impersonation` — superadmin impersonation lifecycle and token failures.
- `integration` — Bitrix24 integration errors, retries, webhook processing and link conflicts.
- `system` — safe technical events that do not fit the above categories.

## Event types

The current implementation reuses existing event types and adds normalized authentication/session names:

- Authentication/session: `login_succeeded`, `login_failed`, `login_blocked_user_denied`, `login_rate_limited`, `logout_completed`, `refresh_failed`, `all_user_sessions_revoked`, password reset/change and first-login events.
- User management: `user_created`, `user_role_assigned`, `user_role_changed`, `user_role_revoked`, `user_company_link_added`, `user_company_link_removed`, `user_blocked`, `user_unblocked`, `bitrix_contact_link_created`, `bitrix_contact_link_changed`, `bitrix_contact_link_removed`, `bitrix_contact_link_verified`, `bitrix_company_link_created`, `bitrix_company_link_changed`, `bitrix_company_link_removed`, `bitrix_company_link_verified`.
- Applications/documents: application submit/status/reassignment events, `active_applications_reassigned`, `application_requires_assignment`, `document_uploaded`, document transfer/retry events and protected document denials.
- Delegation: `delegation_created`, `delegation_activated`, `delegation_cancelled`, `delegation_expired`, `delegation_terminated`, `delegation_activation_failed`, `delegation_access_granted`, `delegation_access_revoked`, `delegated_application_action`, `delegation_cancel_requested`.
- Impersonation: `superadmin_impersonation_started`, `superadmin_impersonation_ended`, `impersonation_token_denied`.
- Integration: `integration_retry_requested`, `integration_error_status_changed`, integration error creation/status/retry events and Bitrix24 link conflict/verification events.

Do not create duplicate event types for the same business action; extend metadata instead.

## Unified representation

`GET /superadmin/audit-events` and `GET /superadmin/audit-events/{event_id}` return a safe normalized shape with:

- event identity: `id`, `event_type`, `category`, `created_at`;
- actors: `actor_user_id`, `effective_user_id` for impersonation;
- targets: `target_type`, `target_id`, `company_id`, `application_id`, `document_id`, `delegation_id`, `integration_error_id`, `impersonation_session_id`;
- outcome: `result`, `reason_code`, `correlation_id`;
- request context: `ip_address`, `user_agent`;
- sanitized `metadata`.

Some normalized fields are stored in `audit_logs.metadata_json` rather than dedicated columns. The public endpoint is the compatibility layer and must remain safe.

## Actor and effective user

Normal events use `actor_user_id` as the authenticated user who performed the action. During superadmin impersonation:

- `actor_user_id` is the superadmin;
- `effective_user_id` is the user whose portal scope is being diagnosed;
- `impersonation_session_id` is present;
- actions must not look like ordinary client actions.

## Correlation ID

The audit helper records the request ID as `correlation_id` when request context is available. Superadmin filters can follow a chain of related actions by this value.

## Metadata minimization and sanitizer

Audit metadata is sanitized centrally before insert. Recursive metadata sanitization masks sensitive keys and token-like strings, including:

- passwords, hashes, tokens, cookies, authorization headers and secrets;
- email, phone, names, comments and descriptions;
- passport, VIN, registration number and bank-account data;
- request/response bodies, document/file content and Bitrix24 payload fragments.

Allowed metadata should prefer stable IDs, status codes, reason codes, counts and safe technical identifiers. Do not store application form fields, vehicle data, route, cargo value, document contents, filenames, full Bitrix24 payloads or webhook secrets.

## Masked denials

Ordinary masked `404` reads are not business audit rows. Security-sensitive denied actions (for example write attempts, protected downloads and role/company manipulation) are audited with a safe reason code.

## Append-only model

Application API exposes read-only audit endpoints for superadmins. There are no PATCH, DELETE, bulk-delete or metadata replacement endpoints for audit rows. Administrative corrections create new audit events instead of modifying old ones.

## Superadmin filters

`GET /superadmin/audit-events` supports backend filtering before pagination by actor, effective user, company, event type, category, result, target type/id, application, delegation, impersonation session, integration error, correlation ID and date range. Export is intentionally out of scope.

## Retention status

Technical logs follow the current operational retention policy of 30 days. Security log retention follows the current technical logging policy. Business audit log retention is not automatically reduced to 30 days; legal/operational retention for critical audit rows is **retention not yet approved** and must be confirmed separately before implementing deletion.

## Boundaries

The audit log is an incident-investigation tool, not a second CRM. It must not expose business contents of Bitrix24 deals, policies, documents, internal comments or insurance applications.
