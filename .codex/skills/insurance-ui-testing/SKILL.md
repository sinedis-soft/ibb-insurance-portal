---
name: insurance-ui-testing
description: Use when validating UI changes in this insurance web app with browser testing, Playwright, screenshots, responsive breakpoints, visual regression checks, layout-shift checks, CTA visibility, font regression checks, spacing consistency, and no-horizontal-scroll assertions.
---

# Insurance UI WebApp Testing Skill

You are responsible for validating UI output using automated browser testing, preferably Playwright when available.

## Goals

Prevent:

- Layout shifts.
- Broken responsive behavior.
- Font regressions.
- Spacing inconsistencies.
- CTA visibility issues.
- Overlapping or unreachable form controls.

## Mandatory coverage for UI changes

Test every meaningful UI change at:

- 360px mobile.
- 768px tablet.
- 1280px desktop.

When the environment lacks browser tooling, state the limitation clearly and run the strongest available substitutes, such as build checks, HTML assertions, CSS assertions, and local route smoke checks.

## Visual regression rules

When browser tooling is available:

- Capture screenshots per breakpoint.
- Compare against the baseline when one exists.
- Flag visible deviations in spacing, typography scaling, button alignment, wrapping, and sticky header behavior.
- Store or report screenshot paths in the final response.

## Critical UI assertions

Check:

- Primary CTA is visible without scroll on desktop when applicable.
- Form submit or continue button is reachable on mobile.
- No overlapping UI elements.
- No horizontal scroll.
- Header, footer, modals, and sticky elements remain usable.
- RTL pages do not break alignment or field order.

## Failure handling

If a test fails:

1. Identify the layout cause.
2. Suggest a structural fix, not a cosmetic patch.
3. Apply the fix if in scope.
4. Re-run the test.

## Output format

Return:

- Test status by command/check.
- Failed components or breakpoints.
- Recommended fix or implemented fix.
- Screenshot references when captured.
- Environment limitations when screenshots or Playwright cannot run.