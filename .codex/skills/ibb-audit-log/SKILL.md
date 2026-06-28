---
name: ibb-audit-log
description: Defines business audit log rules for IBB Insurance Portal. Use when editing user actions, authentication, role assignment, company access, partner visibility, applications, document upload, policy requests, cancellation, change requests, superadmin actions, or Bitrix24 status changes.
---

# IBB Audit Log Skill

## Purpose

Use this skill to ensure business-critical user actions are recorded in a PostgreSQL audit log.

Technical logs and business audit log are different.

Technical logs help developers debug requests.

Business audit log helps answer:

- who did it;
- when it happened;
- from which account;
- from which IP;
- what business object was affected;
- which Bitrix24 entity was involved.

## Required knowledge base

Before changing audit, application, Bitrix24 status sync, partner visibility, document, auth, role, or company access behavior, read:

- `docs/knowledge-base/index.md`;
- `docs/knowledge-base/bitrix24-field-mapping.md`;
- `docs/knowledge-base/mvp-scope.md`;
- `docs/access-control-matrix.md`.

## Storage rule

Business audit log must be stored in PostgreSQL.

Retention period:

- 6 months.

Access:

- superadmin only.

Deletion:

- superadmin must not be able to delete audit log by ordinary UI action.

Technical server logs are separate:

- file/stdout;
- 30 days;
- no personal data;
- used for debugging.

## Audit log fields

Recommended table: `audit_logs`.

Fields:

- id;
- actor_user_id;
- target_user_id;
- company_group_id;
- bitrix_company_id;
- application_id;
- bitrix_deal_id;
- action;
- object_type;
- object_id;
- ip_address;
- user_agent;
- metadata_json;
- created_at.

## What must be audited

Audit these actions:

- login success;
- login failure;
- logout;
- password reset requested;
- password changed;
- one-time login link used;
- user created from Bitrix24 contact;
- user blocked;
- user unblocked;
- role assigned;
- role revoked;
- company access granted;
- company access revoked;
- partner profile created;
- partner-client link created;
- partner-client status changed;
- application draft created;
- application draft changed;
- application submitted;
- Bitrix24 deal created from application;
- Bitrix24 deal creation failed;
- document uploaded;
- document transfer to Bitrix24 succeeded;
- document transfer to Bitrix24 failed;
- document transfer expired after 24 hours;
- policy email request created;
- policy Telegram request created;
- cancellation request created;
- policy change request created;
- application status updated from Bitrix24;
- superadmin impersonation started;
- superadmin impersonation ended.

## What must not be stored in audit metadata

Do not store:

- raw request body;
- full application data;
- full Bitrix24 payload;
- email;
- phone;
- name;
- comments;
- VIN;
- vehicle plate;
- route;
- cargo value;
- document content;
- tokens;
- passwords;
- cookies.

Use internal IDs and sanitized metadata only.

Allowed metadata examples:

```json
{
  "request_id": "req_01JABC",
  "old_status": "in_work",
  "new_status": "policy_issued",
  "source": "bitrix_webhook"
}
```

Forbidden metadata example:

```json
{
  "email": "client@example.com",
  "phone": "+995...",
  "comment": "urgent",
  "vin": "ABC123",
  "filename": "passport_ivanov.pdf"
}
```

## Superadmin impersonation

Superadmin impersonation is high risk.

Always audit:

- who entered;
- target user;
- reason;
- start time;
- end time;
- IP address;
- user agent;
- actions performed during impersonation.

Impersonation must require a reason.

Do not allow silent impersonation.

## Document audit

When a document is uploaded or transferred, audit:

- actor_user_id;
- application_id;
- bitrix_deal_id;
- action;
- transfer_status;
- timestamp.

Do not audit:

- original filename in ordinary audit metadata unless explicitly required;
- document content;
- file path;
- file URL.

Document transfer table may store original_filename separately, but technical logs must not expose it.

## Partner visibility audit

Always audit:

- partner linked to client;
- partner assigned to deal;
- client marked as another partner client;
- partner status changed;
- partner access rejected.

Use IDs, not names.

## Status update audit

When Bitrix24 webhook changes portal-visible status, audit:

- application_id;
- bitrix_deal_id;
- old_portal_status;
- new_portal_status;
- bitrix_stage_id;
- source = bitrix_webhook.

Do not store the full webhook payload.

## Acceptance criteria

This skill is satisfied when:

- business audit log is stored in PostgreSQL;
- audit retention is 6 months;
- superadmin-only access is enforced;
- important business actions are logged;
- superadmin impersonation is fully logged;
- audit log uses internal IDs;
- audit metadata is sanitized;
- audit log cannot be deleted by ordinary UI action.
