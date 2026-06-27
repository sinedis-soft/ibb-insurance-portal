---
name: legal-compliance-ui
description: Use when designing or reviewing insurance UI for EU/PL transparency, legal disclosures, insurer/broker identity, jurisdiction, policy type, coverage/exclusions, complaint paths, pricing disclosure, document requirements, risk communication, or regulated insurance purchase flows.
---

# Legal Compliance UI Layer (Insurance EU / PL)

You are responsible for ensuring UI supports EU/PL insurance transparency and brokerage standards.

This is not legal advice. This is UI enforcement logic for regulated insurance clarity.

## Mandatory disclosures

Every insurance flow must expose, somewhere visible and discoverable:

- Insurer identity.
- Broker or agency identity.
- Jurisdiction, such as EU, PL, GE, or another applicable regime.
- Policy type, such as OC, Green Card, MTPL, or border insurance.
- Coverage scope summary.
- Exclusions summary.
- Complaint or support path.

## Transparency rule

Ensure the user always knows:

- What they are buying.
- From whom they are buying it.
- Under which legal regime.
- When coverage starts.
- Where coverage is valid.

Do not allow hidden legal context.

## Pricing compliance rules

- Show final price before the payment step.
- Make currency explicit.
- Do not introduce fees after the payment trigger.
- Explain conditional pricing.

## Document requirements UI

If documents are required, show:

- Checklist before upload.
- Reason for each document.
- Consequence of each missing document.
- Save-and-continue option when product scope supports it.

Never block progress without explanation.

## Risk communication rules

- Warn about exclusions before purchase.
- Avoid legal jargon without explanation.
- Avoid fear-based wording.
- Keep tone neutral, factual, and non-alarming.

## Compliance anti-patterns

Flag and avoid:

- Hiding insurer details behind clicks.
- Vague “terms apply” text without context.
- Delayed disclosure of exclusions.
- Unclear jurisdiction or coverage territory.