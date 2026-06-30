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

- calm warm ivory background from the MVP brandbook: `#F7F4EC`;
- clean white cards and panels: `#FFFFFF`;
- graphite primary text: `#1E2933`;
- muted medium blue as the primary interaction color: `#2F6F8F`;
- restrained broker gold as brand accent: `#B8945A`;
- light gold for accent borders/dividers: `#E8D8AE`;
- soft blue for selected cards, information states, and active-row backgrounds: `#D9EEF6`;
- green only for successful/active/issued states, using restrained status green (`#DDEFE7` / `#2F6B4F`);
- amber/bronze only for awaiting/expiring/attention states (`#F4E8C8` / `#7A623E`);
- red only for duplicate/error/destructive states (`#F9D7D7` / `#9B1C1C`);
- elegant serif headings paired with readable sans-serif body text;
- thin borders, soft shadows, 8px card radius unless an existing component token says otherwise;
- line icons, preferably from the existing icon library.

Do not introduce green/teal primary CTAs, green navigation, purple/blue gradients, dark dashboard themes, stock-photo decoration, or unrelated SaaS styling.
If an implementation token named `primary` is greenish, teal, emerald, or success-colored, replace it with the MVP muted blue `#2F6F8F`.

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
