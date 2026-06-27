---
name: insurance-seo-page
description: Use for edits to localized product/landing pages, locale routes, static params, SEO metadata, JSON-LD, breadcrumbs, sitemap, robots, hreflang, or canonical URLs.
---

# Insurance SEO Page

AGENTS.md already covers routing, i18n, SEO, and insurance-domain rules. Use this page-specific checklist.

## Preserve

- Existing route architecture and locale behavior unless explicitly requested.
- Existing SEO helpers/dictionaries, `SITE_URL`, static route generation, alternates, breadcrumbs, and JSON-LD patterns.

## Content guardrails

- Keep product pages legally accurate and commercially clear.
- When relevant, cover product, eligibility, documents, territory, start date, term, payment, delivery, restrictions, and support contacts.
- Avoid unsupported claims about coverage, prices, guarantees, refunds, eligibility, claims outcomes, or processing time.

## Verify

For production-impacting page/SEO edits, run `npm run lint`, `npx tsc --noEmit`, and `npm run build`.

## AI Search maintenance

When adding, removing, renaming, or substantially updating a product page, landing page, legal/contact/about page, locale entry point, article route, sitemap/canonical structure, or major page content, also use `$llms-txt-builder`.

Update `public/llms.txt` when the change affects core pages, important evergreen articles, product conditions, geography, limitations, disclaimers, canonical URLs, sitemap priorities, or site-level meaning. Skip `llms.txt` only for minor wording edits and note that decision in the final summary when relevant.

## Report

Changed routes/pages, locales, metadata/JSON-LD impact, `llms.txt` impact, verification results, and legal/SEO assumptions.
