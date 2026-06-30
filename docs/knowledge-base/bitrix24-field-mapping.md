# Bitrix24 Field Mapping Knowledge Base

## Hard Rule

Do not create duplicate Bitrix24 custom fields. Before adding or mapping any Bitrix24 field, fetch the current field inventory:

- `crm.deal.fields`
- `crm.company.fields`
- `crm.contact.fields`

Use the official Bitrix24 REST documentation through `b24-dev-mcp` before writing code that uses or creates Bitrix24 fields.

## Existing Fields That Must Not Be Duplicated

These fields were already observed in Bitrix24 deal exports. Use them if they still exist in the live field inventory.

| Logical field | Bitrix24 field | Entity | Type | Notes |
|---|---:|---|---|---|
| portal_application_id | `UF_CRM_1782659474410` | deal | string | Portal application ID. Do not create another field with the same meaning. |
| portal_application_type | `UF_CRM_1782660209555` | deal | enumeration | Values include `auto`, `cargo`. |
| portal_source | `UF_CRM_1782660734915` | deal | enumeration | Values include `ibb_portal`, `ibb_public_form`, `bitrix_manual`, `api_import`. |
| portal_channel | `UF_CRM_1782660775332` | deal | enumeration | Values include `client_portal`, `partner_portal`, `public_form`, `admin_created`, `bitrix_created`. |
| portal_sync_status | `UF_CRM_1782660821873` | deal | enumeration | Values include `pending`, `synced`, `sync_error`, `retry_required`, `skipped`. |
| portal_last_sync_at | `UF_CRM_1782660834442` | deal | date | Last portal sync timestamp. |
| portal_sync_error | `UF_CRM_1782660852370` | deal | string | Store short sanitized error code only. |
| communication_language | `UF_CRM_1753957395750` | contact | enumeration | Source for portal UI language and email language. |
| agent_broker | `UF_CRM_1686682902533` | deal | enumeration | Existing Agent / Broker field. Do not use as portal partner. |

## Language Field Rule

Do not create a separate `Interface language` field.

Use contact field:

```text
UF_CRM_1753957395750
Language of communication
Entity: contact
Type: enumeration
```

MVP locale mapping:

| Bitrix24 contact language | Portal locale |
|---|---|
| Russian | `ru` |
| Georgian | `ka` |
| empty | `ru` |
| unsupported | `ru` |

If later the portal supports more locales, extend the mapping in code and dictionaries. For MVP, `ru` and `ka` are mandatory.

## Agent / Broker Rule

Do not use `UF_CRM_1686682902533 / Agent / Broker` as the portal partner.

Reason:

- It represents another business concept.
- It may contain internal broker/agent values.
- Portal partner access is a separate visibility and authorization circuit.

If a portal partner field is needed, inventory existing fields first. If no correct field exists, create or map a separate `Portal partner` field and document the mapping.

## System Company Ignore Rule

Always ignore Bitrix24 company ID `1817`.

This company is a Bitrix/system company and must not be treated as a client company, partner client, company access target, application scope, policy scope, or selectable portal company.

When reading contact-company relations, a contact's fallback `COMPANY_ID`, creating `user_company_roles`, listing accessible companies, or checking company access, filter out `1817`.

## Contact Company Relations

Contacts may be linked to multiple companies in Bitrix24.

For portal access sync, read contact-company bindings with `crm.contact.company.items.get` and use every returned `COMPANY_ID` except ignored system IDs such as `1817`.

The legacy contact field `COMPANY_ID` is only a fallback when relation reading fails or returns no usable companies.

Company names shown to users must come from Bitrix24 company `TITLE` cached on `user_company_roles.company_title_cache`; never show the Bitrix technical ID as the client-facing company name.

## Deal Fields To Add Or Map Only After Inventory

These logical fields may be needed, but Codex must first check whether an equivalent field already exists:

| Logical field | Entity | Type | Create if missing | Client visible | Notes |
|---|---|---|---|---|---|
| portal_created_by_user_id | deal | string | yes | no | Internal portal user ID only. No email/name/phone. |
| show_in_portal | deal | boolean | yes | no | Manual visibility flag. Empty means true unless stage is hidden. |
| client_comment | deal | text/string | yes | yes | Public manager comment for client. Do not reuse internal `COMMENTS`. |
| client_action_required | deal | boolean | yes | yes | Client-facing required-action marker. |
| client_required_action | deal | enumeration/string | yes | yes | Stable action code only. |
| portal_partner | deal | CRM binding / smart process binding | yes | no | Portal partner metadata, not authorization source. |
| is_partner_application | deal | boolean | yes | no | True when partner portal created or initiated the application. |
| partner_portal_user_id | deal | string | yes | no | Internal partner portal user ID only. |
| partner_policy_file_allowed | deal | boolean | yes | no | Default false. Supporting permission flag only. |

## Contact Fields To Add Or Map Only After Inventory

| Logical field | Entity | Type | Create if missing | Client visible | Notes |
|---|---|---|---|---|---|
| portal_user_id | contact | string | yes | no | Link Bitrix24 contact to portal user. Do not use email as key. |
| is_portal_user | contact | boolean | yes | no | Visible CRM marker that contact has or may have portal access. |
| communication_language | contact | enumeration | no | no | Use `UF_CRM_1753957395750`; do not create interface-language duplicate. |

## Partner Client Check Fields

Current MVP flow works only with companies. A contact-level field already exists for future individual-person
applications, but it must not be used in the company-only partner client check flow until the individual-person flow is
explicitly designed.

| Logical field | Bitrix24 field | Entity | Type | Notes |
|---|---:|---|---|---|
| future_individual_client_check_status | `UF_CRM_1782757798892` | contact | enumeration | Future field for individual-person applications. Do not use while MVP works only with companies. |
| partner_client_check_status | `UF_CRM_1782757925237` | company | enumeration | Company client check stage. Set to `6479` / `Ожидает проверки` when creating a partner client company check. |
| portal_partner_bitrix_id | `UF_CRM_1777876263` | company | unknown/current inventory required | Send Bitrix24 partner ID here when creating/updating a partner client company check. Do not use as the only authorization source. |

Partner client check status mapping:

| Portal status | Company field item ID | Company field value | Contact future item ID | Contact future value |
|---|---:|---|---:|---|
| `pending` | `6479` | `Ожидает проверки` | `6469` | `Ожидает проверки` |
| `clarification_required` | `6481` | `Требуется уточнение` | `6471` | `Требуется уточнение` |
| `confirmed` | `6483` | `Подтверждён` | `6473` | `Подтверждён` |
| `duplicate_found` | `6485` | `Найден дубль` | `6475` | `Найден дубль` |
| `rejected` | `6487` | `Отклонён` | `6477` | `Отклонён` |

For company partner client checks:

- create or update the Bitrix24 company check with `UF_CRM_1782757925237 = 6479` (`pending`);
- send the Bitrix24 partner ID in `UF_CRM_1777876263`;
- let Bitrix24 robots move the check to later statuses;
- sync later statuses back to the portal through the selected webhook/sync mechanism;
- never allow partner application creation until the portal status is `confirmed`.

## Optional Company Fields

Company fields are optional and only needed if managers must control portal access from Bitrix24:

| Logical field | Entity | Type | Create if missing | Notes |
|---|---|---|---|---|
| portal_enabled | company | boolean | optional | Company has portal access. |
| portal_applications_allowed | company | boolean | optional | Applications through portal are allowed. |
| portal_auto_allowed | company | boolean | optional | Auto applications through portal are allowed. |
| portal_cargo_allowed | company | boolean | optional | Cargo applications through portal are allowed. |
| assigned_partner | company | CRM binding / smart process binding | optional | Permanent client-partner relation, not per-deal partner metadata. |

Do not store application-specific data in company fields: plate number, VIN, route, cargo value, policy number, or application status.

## Recommended Central Mapping

Store all `UF_CRM_*` mappings in one backend module/config, not scattered across handlers.

Example shape:

```python
BITRIX_DEAL_FIELDS = {
    "portal_application_id": "UF_CRM_1782659474410",
    "portal_application_type": "UF_CRM_1782660209555",
    "portal_source": "UF_CRM_1782660734915",
    "portal_channel": "UF_CRM_1782660775332",
    "portal_sync_status": "UF_CRM_1782660821873",
    "portal_last_sync_at": "UF_CRM_1782660834442",
    "portal_sync_error": "UF_CRM_1782660852370",
}

BITRIX_CONTACT_FIELDS = {
    "communication_language": "UF_CRM_1753957395750",
}
```

## Source / Channel Rules

When creating a deal from client portal:

```text
Portal source = ibb_portal
Portal channel = client_portal
```

When creating a deal from partner portal:

```text
Portal source = ibb_portal
Portal channel = partner_portal
is_partner_application = true
partner_portal_user_id = current partner portal user ID
portal_partner = mapped partner CRM entity
```

When creating a deal from public form:

```text
Portal source = ibb_public_form
Portal channel = public_form
```

When syncing a manually created Bitrix24 deal into portal:

```text
Portal source = bitrix_manual
Portal channel = bitrix_created
```

## Sync Status Rules

Before submit to Bitrix24:

```text
Portal sync status = pending
```

After successful create/update:

```text
Portal sync status = synced
Portal last sync at = current datetime
Portal sync error = empty
```

If Bitrix24 returns an error:

```text
Portal sync status = sync_error
Portal last sync at = current datetime
Portal sync error = short sanitized error code only
```

Never write request body, full Bitrix24 response, personal data, document filename, policy number, phone, email, tokens, or webhook URL into `Portal sync error`.

## Visibility Rules

An application is visible in the portal only if:

```text
user has application/company access
AND deal stage is not hidden
AND show_in_portal is not false
```

If `show_in_portal` is empty, treat it as true unless stage mapping says hidden.

## Partner Rules

Partner access is controlled by the portal policy layer. Bitrix24 partner fields are supporting metadata only.

Partner policy file download is allowed only if:

- partner has portal access to the application/deal;
- `partner_policy_file_allowed = true`;
- document/policy access layer allows download.

Default:

```text
partner_policy_file_allowed = false
```

## Safe Logging Rules

Never log:

- request body;
- Bitrix24 full payload or full response;
- contact name;
- email;
- phone;
- plate number;
- VIN;
- policy number;
- document filename;
- cargo value;
- route;
- comments;
- tokens;
- cookies;
- webhook URL.

Allowed in logs:

- request_id;
- method;
- path template;
- status_code;
- duration_ms;
- internal user_id;
- bitrix_company_id;
- bitrix_deal_id;
- application_id;
- error_code;
- logical field mapping key, not sensitive value.

## Field Inventory Report Format

When inventorying fields, produce a report with:

```text
logical_field
section
existing_bitrix_field_code
field_type
create_required
allowed_values
client_visible
notes
```
