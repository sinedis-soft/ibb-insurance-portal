---
name: ibb-safe-logging
description: Defines safe technical logging rules for IBB Insurance Portal. Use when editing request logging, error handling, Bitrix24 integration, webhook processing, file upload, API handlers, or backend services that process user data.
---

# IBB Safe Logging Skill

## Purpose

Use this skill to prevent personal data, insurance application data, documents, comments, and secrets from appearing in technical logs.

IBB Insurance Portal processes sensitive insurance data. Logs must support debugging without exposing client data.

Technical logs must contain request id, method, status, duration, internal IDs, and error codes. They must not contain personal data or full payloads.

## Allowed in technical logs

Technical logs may contain:

- request_id;
- event name;
- method;
- path template;
- status_code;
- duration_ms;
- internal user_id;
- role;
- application_id;
- bitrix_deal_id;
- bitrix_company_id;
- bitrix_contact_id;
- bitrix_category_id;
- bitrix_stage_id;
- transfer_status;
- error_code;
- retry_count.

Example:

```json
{
  "level": "info",
  "event": "request_completed",
  "request_id": "req_01JABC",
  "method": "POST",
  "path": "/api/applications",
  "status_code": 201,
  "duration_ms": 238,
  "user_id": "usr_123",
  "role": "client_executor",
  "application_id": "app_456"
}
```

## Forbidden in technical logs

Never log:

- names;
- surnames;
- email addresses;
- phone numbers;
- Telegram usernames;
- Telegram chat IDs;
- WhatsApp identifiers;
- comments from clients;
- internal Bitrix24 comments;
- request body;
- response body with user data;
- full Bitrix24 request payload;
- full Bitrix24 response payload;
- full Bitrix24 webhook payload;
- vehicle plate number;
- VIN;
- passport data;
- route;
- cargo description;
- cargo value;
- invoice data;
- document filename;
- document content;
- file path visible to user;
- file download URL;
- base64 content;
- access token;
- refresh token;
- reset password token;
- one-time login token;
- cookies;
- authorization headers;
- Bitrix24 webhook URL;
- database URL with password.

Bad example:

```python
logger.info("application_submitted", extra={"payload": request_body})
```

Good example:

```python
logger.info(
    "application_submitted",
    extra={
        "request_id": request_id,
        "application_id": application.id,
        "bitrix_deal_id": application.bitrix_deal_id,
        "user_id": current_user.id,
        "role": current_user.role,
    },
)
```

## Request logging rule

Request logs must contain only:

- request_id;
- method;
- path template;
- status_code;
- duration_ms;
- internal user_id, if authenticated;
- role, if authenticated.

Do not log:

- query string if it may contain user data;
- headers;
- cookies;
- request body;
- response body.

## Error logging rule

Errors must be logged with sanitized error codes.

Allowed:

```json
{
  "event": "bitrix_upload_failed",
  "request_id": "req_01JABC",
  "application_id": "app_456",
  "bitrix_deal_id": "12345",
  "error_code": "BITRIX_UPLOAD_FAILED",
  "status_code": 502
}
```

Forbidden:

```json
{
  "event": "bitrix_upload_failed",
  "payload": "...",
  "client_email": "...",
  "filename": "passport_ivanov.pdf",
  "bitrix_webhook_url": "..."
}
```

## Bitrix24 logging rule

When logging Bitrix24 integration, log only technical IDs and sanitized error codes.

Allowed:

- bitrix_deal_id;
- bitrix_company_id;
- bitrix_contact_id;
- bitrix_category_id;
- bitrix_stage_id;
- status_code;
- error_code;
- duration_ms.

Forbidden:

- full Bitrix24 payload;
- company name;
- contact name;
- email;
- phone;
- document names;
- comments;
- webhook URL.

## File upload logging rule

Technical file upload logs may contain:

- request_id;
- application_id;
- bitrix_deal_id;
- file_size;
- mime_type;
- file_extension;
- transfer_status;
- error_code.

Technical file upload logs must not contain:

- original filename;
- file content;
- base64;
- document URL;
- local temp path exposed to user;
- document preview;
- passport data;
- vehicle data.

`original_filename` may be stored only in `document_transfer_logs`, not in ordinary technical request logs.

## Webhook logging rule

Webhook logs may contain:

- request_id;
- event_type;
- bitrix_deal_id;
- bitrix_category_id;
- bitrix_stage_id;
- processing_status;
- error_code.

Never log full webhook payload.

## Development environment rule

Unsafe logging is forbidden even in development.

Do not add temporary debug logs with:

- request body;
- Bitrix24 payload;
- token;
- document content;
- personal data.

Temporary debug logs are frequently forgotten and later reach production.

## Required tests

Add tests that prove:

- request body is not logged;
- email is not logged;
- phone is not logged;
- comments are not logged;
- VIN is not logged;
- vehicle plate is not logged;
- document filename is not logged in technical logs;
- Bitrix24 webhook payload is not logged fully;
- tokens are not logged;
- request_id exists in request logs.

## Acceptance criteria

This skill is satisfied when:

- technical logs contain request_id, method, status, duration;
- technical logs use internal IDs, not personal data;
- no request body is logged;
- no full Bitrix24 payload is logged;
- no secrets are logged;
- no document filename or content is logged in technical logs;
- unsafe logging tests pass.
