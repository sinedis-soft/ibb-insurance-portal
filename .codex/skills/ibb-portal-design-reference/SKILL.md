---
name: ibb-portal-design-reference
description: Use when designing, implementing, reviewing, or refactoring IBB Insurance Portal frontend screens, dashboards, landing/login pages, policy views, application forms, partner/client portals, mobile layouts, visual tokens, or placeholder/demo data based on the provided IBB page sketches.
---

# IBB Portal Design Reference

Use this skill as the project-specific design memory for IBB Insurance Portal.

The sketches are directional product references, not pixel-perfect specifications. Preserve the visual language, hierarchy, content model, and responsive behavior; adapt spacing and components to the actual codebase and accessibility requirements.

## Required Context

Before significant frontend work, read:

- `references/screen-sketches.md` for normalized page data, component patterns, mobile behavior, and demo content.

Use the assets only when visual inspection is needed:

- `assets/public-login-landing.png`
- `assets/client-dashboard.png`
- `assets/partner-dashboard.png`
- `assets/policies-list-details.png`
- `assets/new-application-flow.png`

## Design Contract

Apply the IBB visual system:

- calm white/off-white surfaces;
- deep navy as the primary interaction color;
- restrained gold as brand accent and warning/attention accent;
- light blue selection states;
- green only for successful/active/issued states;
- red only for duplicate/error/destructive states;
- elegant serif headings paired with readable sans-serif body text;
- thin borders, soft shadows, 8px card radius unless an existing component token says otherwise;
- line icons, preferably from the existing icon library.

Do not introduce green primary CTAs, purple/blue gradients, dark dashboard themes, stock-photo decoration, or unrelated SaaS styling.

## Data Rules

Treat all sketch names, emails, policy IDs, counts, and dates as demo data only.

When implementing:

- pull real business data from Bitrix24/API contracts where available;
- keep demo data isolated in mocks, stories, fixtures, or clearly named seed/demo modules;
- never hardcode personal data into backend logs, tests that imply real users, or persistent production tables;
- keep Bitrix24 as source of truth for companies, contacts, policies, applications, documents, and statuses.

## Skill Order

Use this skill together with:

- `insurance-ui-skill` for general insurance UI structure;
- `insurance-ui-review` for review/fix tasks;
- `insurance-ui-testing` for screenshot and responsive verification;
- `legal-compliance-ui` for policy/application disclosure screens;
- `multi-language-ux-enforcement` and `multilingual-dictionaries` when UI copy is localized.
