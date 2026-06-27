---
name: multilingual-dictionaries
description: Use for edits to locale dictionaries, locale definitions, localized UI copy, SEO copy, or insurance/legal/privacy/cookie translations.
---

# Multilingual Dictionaries

AGENTS.md already defines repo-wide i18n and safety rules. Use this focused checklist for dictionary work.

## Checklist

- Preserve dictionary shapes, keys, exported getters, and TypeScript types.
- Update every relevant implemented locale. For the current IBB Portal MVP, `ru` and `ka` are mandatory when localized copy exists.
- Avoid single-language literals in shared components.
- Keep insurance/legal/privacy/cookie terms natural and legally careful, not literal machine translations.
- Keep SEO copy aligned with existing SEO dictionaries/helpers.

## Verify

- Run `npx tsc --noEmit`.
- Run any project-specific locale consistency checks when they exist.

## Report

Files/locales changed, missing locales, assumptions, translation/legal risks, and verification results.
