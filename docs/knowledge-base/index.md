# IBB Portal Knowledge Base

This directory is the project knowledge base that Codex must consult before making architectural,
Bitrix24, access-control, logging, audit, localization, or portal workflow changes.

## Required Reading Rule

Before changing this project, read the relevant knowledge base file:

- [bitrix24-field-mapping.md](bitrix24-field-mapping.md) for Bitrix24 fields, CRM sync, portal source/channel, partner metadata, and safe logging around CRM payloads.
- [mvp-scope.md](mvp-scope.md) for MVP boundaries, what stays in Bitrix24, what the portal may store, and cargo application scope.
- [../access-control-matrix.md](../access-control-matrix.md) for role/action authorization rules.

If the task touches Bitrix24 fields, always verify current Bitrix24 REST docs and live fields before creating or using custom fields.

## Core Principles

- IBB Portal must not become a second CRM.
- Bitrix24 remains the business system of record for companies, contacts, deals, policies, documents, stages, internal comments, and operator work.
- The portal stores technical links, auth/session state, access-control state, drafts, safe sync/cache metadata, document transfer metadata, and business audit events.
- Technical logs must stay dry and sanitized.
- Business audit log is a separate PostgreSQL journal of business actions.
- Do not hardcode one UI language in source code. Use RU/KA dictionaries and stable error codes.

