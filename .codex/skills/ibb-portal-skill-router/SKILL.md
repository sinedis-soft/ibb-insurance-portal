---
name: ibb-portal-skill-router
description: Explains when to apply IBB Portal project skills. Use before editing CI, logging, secrets, audit log, Bitrix24 integration, authentication, file upload, user actions, access control, or backend/frontend project structure.
---

# IBB Portal Skill Router

## Purpose

Use this skill to decide which IBB Portal project skill must be applied before changing code.

IBB Insurance Portal must not become a second CRM. Bitrix24 remains the source of truth for business data: companies, contacts, deals, policies, documents, stages, internal comments, and operator work.

The portal stores only technical data required for authentication, access control, Bitrix24 links, integration status, document transfer status, safe user actions, and audit log.

## Always check the task type first

Before editing code, determine whether the task touches any of these areas:

- CI pipeline;
- tests;
- build configuration;
- logging;
- error handling;
- secrets;
- environment variables;
- authentication;
- password reset;
- one-time login links;
- Bitrix24 integration;
- file upload;
- document transfer;
- user roles;
- access control;
- partner visibility;
- audit log;
- webhook processing.

If yes, apply the relevant IBB skill below.

## Skill selection

### Use `ibb-ci-pipeline`

Apply when changing:

- GitHub Actions;
- CI/CD pipeline;
- Docker build;
- backend lint/test/build;
- frontend lint/typecheck/build;
- dependency audit;
- test commands;
- build scripts;
- package scripts;
- pre-merge checks.

### Use `ibb-safe-logging`

Apply when changing:

- logging middleware;
- request logging;
- error logging;
- Bitrix24 integration logging;
- file upload logging;
- webhook logging;
- API handlers;
- exception handlers;
- backend services that receive user data.

### Use `ibb-secret-management`

Apply when changing:

- `.env`;
- `.env.example`;
- config files;
- Bitrix24 webhook URL;
- tokens;
- JWT;
- cookies;
- SMTP settings;
- database connection;
- Redis connection;
- password reset tokens;
- one-time login tokens;
- CI secrets.

### Use `ibb-audit-log`

Apply when changing:

- user actions;
- login/logout;
- failed login;
- password reset;
- first login;
- user creation;
- role assignment;
- company access;
- partner access;
- application creation;
- document upload;
- policy request;
- cancellation request;
- change request;
- superadmin impersonation;
- blocking users;
- Bitrix24 sync events that affect user-visible status.

## Conflict rule

If several skills apply, use all relevant skills.

Example:

A task changes Bitrix24 webhook processing and logs webhook failures.

Apply:

- `ibb-safe-logging`;
- `ibb-secret-management`;
- `ibb-audit-log`, if the webhook changes user-visible status;
- `ibb-ci-pipeline`, if CI checks are changed.

## Project-specific hard rules

Never log:

- request body;
- response body with user data;
- full Bitrix24 payload;
- names;
- email;
- phone;
- comments;
- vehicle plate;
- VIN;
- route;
- cargo value;
- document filename;
- document content;
- tokens;
- cookies;
- passwords;
- webhook URLs.

Never store documents permanently in the portal.

Never create CRM-like tables that duplicate Bitrix24 companies, contacts, policies, operator tasks, chats, commissions, or internal CRM history.

Always use internal IDs in logs:

- request_id;
- user_id;
- application_id;
- bitrix_deal_id;
- bitrix_company_id;
- bitrix_contact_id;
- status_code;
- duration_ms;
- error_code.

## Before finishing any code change

Check:

- CI still passes;
- unsafe logging was not added;
- secrets are not committed;
- audit log is updated for business-critical actions;
- access control was not weakened;
- Bitrix24 remains the business data source.
