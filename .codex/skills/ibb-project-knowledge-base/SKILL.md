---
name: ibb-project-knowledge-base
description: Requires Codex to consult the IBB Insurance Portal project knowledge base before project work. Use for IBB Portal architecture, Bitrix24 field mapping, CRM sync, MVP scope, cargo/auto applications, access control, safe logging, audit log, localization, or any backend/frontend change in this repository.
---

# IBB Project Knowledge Base

## Required First Step

Before changing IBB Insurance Portal code or documentation, read the relevant project knowledge base:

- `docs/knowledge-base/index.md` for the routing overview.
- `docs/knowledge-base/bitrix24-field-mapping.md` before any Bitrix24 field, CRM sync, portal source/channel, partner metadata, or Bitrix24 logging change.
- `docs/knowledge-base/mvp-scope.md` before application flow, cargo/auto, access-control, audit, logging, or MVP boundary changes.
- `docs/access-control-matrix.md` before authorization and role-policy changes.

Do not rely on memory if a knowledge-base file covers the topic.

## Bitrix24 Rule

For Bitrix24 work:

1. Use `b24-dev-mcp` official REST docs before writing code.
2. Inventory live fields with `crm.deal.fields`, `crm.company.fields`, and `crm.contact.fields` before creating or mapping custom fields.
3. Do not create duplicate fields.
4. Store `UF_CRM_*` mappings in one backend config/module.

## Non-Negotiable Project Rules

- Do not create a Bitrix24 `Interface language` field; use contact `UF_CRM_1753957395750`.
- Do not use `UF_CRM_1686682902533 / Agent / Broker` as portal partner.
- Do not duplicate existing portal deal fields: application ID, application type, source, channel, sync status, last sync at, sync error.
- Do not treat Bitrix24 metadata fields as the only authorization source.
- Do not log personal, commercial, document, route, cargo value, token, cookie, webhook, request body, or full Bitrix24 payload data.
- Do not hardcode one UI language in source code.

