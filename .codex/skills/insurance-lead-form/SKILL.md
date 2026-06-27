---
name: insurance-lead-form
description: Use for edits to insurance application forms, lead/application submit endpoints, contact/policyholder/vehicle fields, multipart FormData, vehicles[index][field], file uploads, validation, or submit states.
---

# Insurance Lead Form

AGENTS.md and IBB skills already cover global frontend, privacy, Bitrix24, and verification rules. This skill focuses on insurance form/API compatibility.

## Preserve

- Field names consumed by the current submit endpoint, including `vehicles[index][field]` when that contract exists.
- Multipart `FormData` contract unless the user explicitly asks to change it.
- Current upload type policy: accept images/PDFs and reject archives/audio/video.
- Client/API upload-limit alignment.
- Native validation where used (`required`, input types, `checkValidity`, `reportValidity`).
- Accessible labels, focus visibility, mobile layout, and clear loading/error/success/partial-success states.

## Verify

Run `npm run lint` and `npx tsc --noEmit` for code edits. When relevant, manually review required-field, add/remove vehicle, file rejection, success, and error paths.

## Report

Changed files, API contract impact, validation/upload changes, verification results, and risks.
