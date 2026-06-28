---
name: multi-language-ux-enforcement
description: Use when enforcing multilingual UX consistency or adding/editing any user-visible text in frontend/backend code. Applies to localized UI states, CTAs, warnings, legal disclaimers, glossary terminology, error handling, email copy, status labels, RTL behavior, text expansion, and especially preventing hardcoded single-language UI text, fallback English, and partial translations.
---

# Multi-language UX Enforcement Engine

You are responsible for enforcing strict multilingual consistency across all UI states.

## Core rule

Every UI state must exist in all supported languages. No partial localization is allowed unless explicitly approved and reported.

Supported locales are the locales implemented by this repository. For the current IBB Portal MVP, treat `ru` and `ka` as mandatory; update any additional implemented locale when it exists in code.

## Absolute hardcode ban

Do not hardcode user-visible text in product code in only one language.

This is forbidden in frontend and backend:

- JSX/TSX literals such as `<button>Войти</button>` or `<h1>პაროლის შეცვლა</h1>`.
- Inline page dictionaries inside components.
- API response messages written directly in routers or handlers.
- Email subjects/bodies written directly in service code.
- Status labels, role labels, validation messages, toast text, empty states, placeholders, and CTA labels outside localization dictionaries/templates.

Instead:

- Put frontend copy in locale dictionaries such as `frontend/messages/ru.json` and `frontend/messages/ka.json`.
- Put backend copy in backend i18n dictionaries/templates.
- Use stable keys and stable `error_code` values in business logic.
- Resolve localized text at the edge: UI render, API error response, email render.
- Add or update every mandatory locale (`ru`, `ka`) in the same change.

Allowed hardcoded strings:

- Technical codes, enum values, route paths, CSS class names, test data, migration names, log action names, and audit action names.
- Brand names such as `IBB Insurance Portal` when they are intentionally not translated.
- Comments explaining implementation details.

## Language consistency rules

Ensure the same across all languages:

- Meaning.
- CTA intent.
- Warning severity.
- Legal meaning in disclaimers.
- Error cause and recovery action.

## Forbidden patterns

Do not allow:

- Mixed languages in one screen.
- Fallback English inside localized UI.
- Untranslated error messages.
- Partial UI translation.
- One-language-only UI literals in `.tsx`, `.ts`, routers, handlers, or email services.
- Building localization keys from user input.
- Logging localized text together with personal data.

## Translation priority

When prioritizing work, handle in this order:

1. Legal and compliance text.
2. Errors and warnings.
3. CTAs and actions.
4. Labels and metadata.
5. Decorative text.

## Terminology control

Key terms must have one canonical translation per language:

- Insurance policy.
- Coverage.
- Insurer.
- Broker.
- Claim.
- Validity period.
- Deductible / excess.

If no glossary exists, identify the need and avoid introducing inconsistent synonyms.

## UX consistency rules

Across languages:

- Layout must not shift significantly.
- Button sizes must remain stable.
- Text expansion must not break UI.
- Long or complex-script languages such as RU and KA should be checked early.
- RTL pages must preserve reading order, field order, and alignment.

## Error handling rules

All error messages must:

- Be localized.
- Be actionable.
- Explain cause and fix.
- Avoid technical jargon.
- Preserve stable `error_code`; frontend logic must branch on `error_code`, not message text.

Use this pattern:

1. What happened.
2. Why it happened.
3. What the user should do next.

## Anti-patterns

Flag and avoid:

- Translation after design.
- Hardcoded English UI.
- Hardcoded Russian-only or Georgian-only UI.
- Inconsistent terminology across pages.
- Untranslated system errors.

## Required checks

Before finishing a change that touches UI, auth errors, statuses, validation, email, or dictionaries:

- Search for Cyrillic/Georgian text outside dictionaries/templates/tests.
- Run project i18n checks when available, for example `npm run i18n:check`.
- Run frontend lint/typecheck/build when frontend files changed.
- Run backend tests when backend i18n or error responses changed.
- Report any intentionally deferred translations explicitly.
