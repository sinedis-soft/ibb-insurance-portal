---
name: multi-language-ux-enforcement
description: Use when enforcing multilingual UX consistency across all supported locales, localized UI states, CTAs, warnings, legal disclaimers, glossary terminology, error handling, RTL behavior, text expansion, or preventing fallback English and partial translations.
---

# Multi-language UX Enforcement Engine

You are responsible for enforcing strict multilingual consistency across all UI states.

## Core rule

Every UI state must exist in all supported languages. No partial localization is allowed unless explicitly approved and reported.

Supported locales are the locales implemented by this repository. For the current IBB Portal MVP, treat `ru` and `ka` as mandatory; update any additional implemented locale when it exists in code.

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

Use this pattern:

1. What happened.
2. Why it happened.
3. What the user should do next.

## Anti-patterns

Flag and avoid:

- Translation after design.
- Hardcoded English UI.
- Inconsistent terminology across pages.
- Untranslated system errors.
