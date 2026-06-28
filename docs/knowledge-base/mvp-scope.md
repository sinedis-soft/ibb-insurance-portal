# IBB Portal MVP Scope Knowledge Base

## Scope Goal

Keep the first delivery manageable: roughly 16-24 weeks of MVP work instead of a full 6-9 month B2B portal.

MVP keeps an end-to-end flow:

- login;
- companies;
- applications;
- documents;
- Bitrix24 sync;
- statuses;
- policies;
- partner access;
- audit log.

Move these outside the first launch unless explicitly requested:

- chats;
- external public API;
- complex notification workflows;
- tariff calculations that replace insurer/Bitrix24 logic.

## System Boundary

IBB Portal is an external client and partner portal. It must not become a second CRM.

Bitrix24 remains the source of truth for:

- companies;
- contacts;
- deals;
- policies;
- documents;
- processing stages;
- internal comments;
- operator work.

The portal may store:

- authentication and session state;
- user-company roles and partner links;
- application drafts;
- portal-visible status/cache data;
- Bitrix24 technical links;
- document transfer metadata;
- safe user actions;
- PostgreSQL business audit log.

## Cargo Application Scope

Cargo application MVP supports three application types:

- `single_shipment`;
- `contract_coverage`;
- `certificate`.

Use `portal_applications` for cargo drafts:

```text
application_type = cargo
portal_status = draft
bitrix_category_id = 19
bitrix_deal_id = null until submit creates or links a Bitrix24 deal
bitrix_company_id = selected company context
created_by_user_id = current user ID
draft_data_json = structured cargo draft payload
```

Minimum cargo draft structure:

```json
{
  "cargo_application_type": "single_shipment",
  "route": {
    "country_from": "GE",
    "country_to": "PL",
    "route_description": "Georgia - Turkey - EU"
  },
  "cargo": {
    "cargo_type": "general_cargo",
    "cargo_description": "General cargo",
    "cargo_value": "50000.00",
    "currency": "EUR"
  },
  "transport": {
    "transport_type": "road",
    "carrier_name": "Carrier name",
    "vehicle_plate": "AB1234",
    "departure_date": "2026-09-10"
  },
  "contract": {
    "bitrix_contract_deal_id": "12345",
    "contract_number": "CARGO-2026-01",
    "is_active_contract": true
  },
  "certificate": {
    "is_certificate_requested": true
  },
  "comment": "Client comment"
}
```

Do not log `draft_data_json`.

Do not store in draft payload:

- base64 documents;
- full Bitrix24 payload;
- internal comments;
- tariff calculations;
- commissions;
- excessive personal data.

## Cargo Validation Rules

For `single_shipment`, require:

- company context;
- contact/current user;
- application type;
- country from;
- country to;
- cargo type or cargo description;
- cargo value;
- currency;
- transport type;
- at least one document on submit when submit is implemented.

For `contract_coverage`, require:

- active contract marker;
- contract number or Bitrix24 contract deal ID;
- cargo/application details needed by business process.

For `certificate`, require:

- active contract marker;
- contract number or Bitrix24 contract deal ID;
- certificate requested;
- route/cargo/transport data needed to issue a certificate.

## Access-Control Principles

- `client_admin` and `client_executor` may create/edit drafts for companies where they have active access.
- `client_viewer` is read-only and must not create/edit/submit.
- Pending or revoked company access blocks draft create/update/submit.
- A user must not restore or update another company's draft.
- A guessed foreign application ID should return 404, not leak existence.
- Partner endpoints must be separate from normal client endpoints when partner workflows are added.

## Localization Principles

- Supported MVP locales: `ru`, `ka`.
- Default locale: `ru`.
- Do not hardcode one visible language in frontend/backend code.
- Use stable error codes and locale dictionaries.
- Contact language comes from Bitrix24 contact field `UF_CRM_1753957395750 / Language of communication`.
- Do not create a separate Bitrix24 `Interface language` field.

## Logging And Audit Principles

Technical logs must be dry and sanitized. Business audit log is a separate PostgreSQL journal.

Never log:

- request body;
- full Bitrix24 payload;
- names;
- email;
- phone;
- plate number;
- VIN;
- route;
- cargo value;
- document filename;
- comments;
- tokens;
- cookies;
- webhook URL.

Audit business-critical actions with internal IDs and sanitized metadata only.

