---
name: tariff-calculator
description: Use for edits to insurance tariff values, pricing modules, getPolicyPrice-like functions, formatCurrency-like helpers, calculator UI, or vehicle type, term, region, and currency logic.
---

# Tariff Calculator

AGENTS.md already marks tariffs as sensitive business logic. This skill is the focused pricing checklist.

## Rules

- Do not change tariff values unless explicitly requested.
- Keep calculation/formatting centralized in the existing pricing module; do not duplicate tariff logic in components.
- Preserve existing missing/invalid-price and currency-formatting behavior unless explicitly asked.
- Document any change to pricing, rounding, supported terms, vehicle categories, currencies, or display locale.

## Verify

Run `npm run lint` and `npx tsc --noEmit` for code edits. For pricing behavior changes, manually check representative valid and invalid vehicle/term combinations.

## Report

Changed files, pricing/calculation impact, representative checks, verification results, and business risks.
