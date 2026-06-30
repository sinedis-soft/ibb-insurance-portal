---
name: ibb-portal-skill-router
description: Explains when to apply IBB Portal project skills. Use before editing CI, logging, secrets, audit log, Bitrix24 integration, authentication, file upload, user actions, access control, frontend UI, SEO, localization, copy, forms, tariffs, or backend/frontend project structure.
---

# IBB Portal Skill Router

## Purpose

Use this skill to decide which IBB Portal project skill must be applied before changing code.

IBB Insurance Portal must not become a second CRM. Bitrix24 remains the source of truth for business data: companies, contacts, deals, policies, documents, stages, internal comments, and operator work.

The portal stores only technical data required for authentication, access control, Bitrix24 links, integration status, document transfer status, safe user actions, and audit log.

## Project knowledge base is mandatory

Before applying any IBB project skill, first apply `ibb-project-knowledge-base` and read the relevant files under `docs/knowledge-base/`.

At minimum, read:

- `docs/knowledge-base/index.md` for routing;
- `docs/knowledge-base/bitrix24-field-mapping.md` for Bitrix24 fields, CRM sync, source/channel, partner metadata, and safe CRM logging;
- `docs/knowledge-base/mvp-scope.md` for application flows, MVP boundaries, cargo/auto scope, logging, audit, and localization rules;
- `docs/access-control-matrix.md` for authorization changes.

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
- frontend UI;
- frontend color tokens or CSS palette;
- project design references;
- insurance forms;
- SEO, robots, sitemap, hreflang, or llms.txt;
- localized copy or dictionaries;
- public marketing/product copy;
- tariff calculators;
- legal/compliance disclosures.

If yes, apply the relevant IBB skill below.

## Skill selection

### Use `ibb-project-knowledge-base`

Apply before any IBB Portal repository work, especially architecture, Bitrix24 integration, CRM field mapping, MVP scope, application flows, access control, audit, logging, localization, or backend/frontend changes.

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

### Use `insurance-ux-governance`

Apply as the top-level coordinator when a frontend task combines several product-surface concerns:

- UI design or review;
- forms;
- SEO pages;
- localization;
- legal/compliance copy;
- conversion;
- screenshot-based design;
- UI testing.

Use the specific skills below alongside it when their triggers apply.

### Use `insurance-ui-skill`

Apply when designing or implementing high-trust insurance/fintech UI, dashboards, product pages, calculators, forms, trust sections, or multilingual interfaces.

### Use `ibb-portal-design-reference`

Apply when designing, implementing, or reviewing IBB Portal screens against the provided page sketches, including landing/login, client dashboard, partner dashboard, policies, application wizard, mobile layouts, visual tokens, or demo data.

For CSS and design-token changes, enforce the MVP brandbook palette: warm ivory background, white cards, muted blue primary, broker gold accents, soft blue selection states, and status green only for success/active/issued. Green or teal primary CTAs are forbidden.

### Use `insurance-ui-review`

Apply when reviewing or improving product pages, calculators, forms, contact pages, mobile layout, accessibility, trust elements, or conversion flow.

### Use `insurance-ui-testing`

Apply when validating frontend UI with browser testing, screenshots, responsive checks, layout shift checks, CTA visibility, no-horizontal-scroll checks, or visual regression checks.

### Use `screenshot-ui-design`

Apply when a user provides screenshots or asks to imitate the structure of premium fintech/insurance UI. Extract structure only; do not copy branding.

### Use `insurance-lead-form`

Apply when editing insurance application forms, lead/application submit endpoints, contact/policyholder/vehicle fields, multipart form data, file uploads, validation, or submit states.

Also apply:

- `ibb-safe-logging` if the form handles personal data, files, Bitrix24 payloads, or errors;
- `ibb-secret-management` if endpoint configuration or tokens are involved;
- `ibb-audit-log` if a submitted action becomes a business action.

### Use `tariff-calculator`

Apply when editing insurance tariffs, pricing modules, policy price helpers, currency formatting, calculator UI, vehicle type, term, region, or currency logic.

### Use `insurance-seo-page`

Apply when editing localized product/landing pages, SEO metadata, JSON-LD, breadcrumbs, sitemap, robots, hreflang, canonical URLs, or public route structure.

### Use `llms-txt-builder`

Apply when adding, removing, renaming, or substantially updating core public pages or when the task mentions `llms.txt`, AI Search, LLM-readable Markdown pages, AI crawlers, ChatGPT Search, Perplexity, Claude, Gemini, or AI optimization.

### Use `multi-language-ux-enforcement`

Apply when enforcing multilingual UX consistency across supported locales, adding/editing any user-visible text, UI states, CTAs, warnings, legal disclaimers, error handling, text expansion, or fallback-language prevention. Also apply whenever there is a risk of hardcoding Russian-only, Georgian-only, or English-only text in code.

### Use `multilingual-dictionaries`

Apply when editing locale dictionaries, locale definitions, localized UI copy, SEO copy, insurance/legal/privacy/cookie translations, or shared copy keys.

### Use `legal-compliance-ui`

Apply when designing or reviewing insurance UI disclosures around insurer/broker identity, jurisdiction, policy type, coverage, exclusions, complaints, pricing disclosure, documents, or regulated purchase flows.

### Use `conversion-optimization`

Apply when changing or reviewing funnel conversion, CTA placement, form step order, microcopy, trust element positioning, pricing presentation, payment initiation, drop-off recovery, or application completion.

### Use `copywriter-article-reviewer`

Apply when reviewing or improving commercial articles, landing page copy, service descriptions, publication-ready copy, clarity, credibility, conversion usefulness, or regulated-topic risk.

### Use `kazakhstan-human-copywriter`

Apply only when copy is specifically for Kazakhstan context, Kazakhstan routes, Kazakhstan audience, or Kazakhstan-focused insurance content.

## Conflict rule

If several skills apply, use all relevant skills.

Example:

A task changes Bitrix24 webhook processing and logs webhook failures.

Apply:

- `ibb-safe-logging`;
- `ibb-secret-management`;
- `ibb-audit-log`, if the webhook changes user-visible status;
- `ibb-ci-pipeline`, if CI checks are changed.

Donor skill `privacy-and-logging` is intentionally not included in this project because `ibb-safe-logging` and `ibb-secret-management` are stricter and more specific. Do not recreate or add it unless the IBB-specific safety skills are being replaced deliberately.

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

Always ignore Bitrix24 company ID `1817`; it is a system company and must not be used for portal company access, partner scope, application scope, or selectable company lists.

Contacts can be linked to multiple Bitrix24 companies. For access sync, use `crm.contact.company.items.get`; contact `COMPANY_ID` is fallback only. Client-facing screens must display cached Bitrix company `TITLE`, not raw technical company IDs.

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
