# Mobile and PWA checklist

## Audited breakpoints

- 320 × 568 — iPhone SE / smallest supported width.
- 360 × 800 — Android small.
- 375 × 812 — iPhone 13 mini class.
- 390 × 844 — iPhone 13/14 class.
- 412 × 915 — Android large.
- 768 × 1024 — tablet portrait.
- 667–932 px landscape — compact landscape.

## Findings and fixes

| Severity | Screen | Viewport | Problem | Fix | Design-system change |
| --- | --- | --- | --- | --- | --- |
| High | workspace/auth/application/admin pages | 320–412 | desktop padding and wide panels could create cramped content | common mobile shell/panel rules, responsive heading sizing, safe-area padding | yes, global responsive tokens |
| High | application/admin/policy tables | 320–412 | grid/table rows could compress into unreadable columns or overflow document | mobile card/list conversion for grid rows and contained scroll for real tables | yes, shared table/list pattern |
| High | dashboard header | 320–900 | company selector and user menu could exceed header width | sticky compact header, truncated company selector, hidden secondary logout label on smallest width while avatar remains visible | yes, shared header pattern |
| Medium | document upload | 320–412 | selected files/actions could wrap poorly | document rows and inline actions become single-column full-width touch targets | yes, shared document/action pattern |
| Medium | partner/client/admin forms | 320–412 | two-column forms too narrow for touch input | all form grids collapse to one column; inputs stay 16 px minimum | yes, shared form pattern |
| Medium | PWA | all | no install manifest/offline shell/service worker policy | added manifest, icons, offline page, service worker with private-route network-only policy | no |

## Manual scenarios

| Scenario | Role | Viewports | Browser/emulation | Steps | Expected result | Status | Known limitations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Login / logout / session expired | all | 320, 360, 390, 412, 768 | Chrome responsive, Safari-equivalent viewport | Open `/`, login, logout, reload expired session | Auth panels fit, controls are 44 px+, no horizontal overflow | Prepared | Requires real browser/device pass before release |
| First-login and reset links | unauthenticated | 320, 390 | Chrome responsive | Open `/first-login` and `/reset-password` with token parameter | Form labels remain visible, 16 px inputs, errors fit viewport | Prepared | Token validity depends on backend fixture |
| Application list/detail | client executor/admin | 320, 360, 412, 768 | Chrome responsive | Open list, filter, open detail | Rows become cards, detail grid collapses, actions reachable | Prepared | Backend data needed for full action validation |
| Auto/cargo create and submit | client executor/admin/partner | 320, 390, 768 | Chrome responsive | Fill required fields, save draft, submit | Form grids collapse, buttons remain reachable, loading disables double-submit | Prepared | No offline submit by design |
| Document upload/download denial | client executor/admin/partner | 320, 412 | Chrome responsive | Select file/photo, upload, delete or download if allowed | Upload control visible, selected file state fits, no document cache | Prepared | Device camera picker must be verified on real mobile OS |
| Delegations | client executor/admin | 360, 768 | Chrome responsive | Open list/detail and cancellation action if available | Cards/detail fit without horizontal document overflow | Prepared | No standalone delegation access beyond MVP policy |
| Partner client flow | partner | 320, 412, 768 | Chrome responsive | List/create client, update data, create partner application | Partner form/list collapse cleanly, no other-partner data leaked | Prepared | Bitrix24 status webhooks require integration environment |
| Superadmin users/audit/errors/email deliveries | superadmin | 320, 412, 768 | Chrome responsive | Open lists/details, use pagination/filter/retry where allowed | Tables are contained or card-like, buttons wrap and remain accessible | Prepared | Dense audit tables use contained horizontal scroll by design |
| PWA install/start/offline/update | all | mobile browser | Chrome Android/Safari iOS/Samsung Internet | Install, launch standalone, go offline, logout after reconnect | Manifest installable, offline page has no private data, service worker network-only for private routes | Prepared | iOS install prompt is browser-controlled; no custom install funnel |

## PWA privacy review

- Service worker caches only `/offline.html`, manifest and public icons during install.
- Private app/API routes are explicitly network-only: auth, applications, documents, superadmin, delegations, partner, policies.
- No POST/PUT/PATCH/DELETE responses are cached.
- No background sync, offline submission, document caching or signed URL caching is implemented.
- No access/refresh token handling is added to JavaScript; httpOnly cookies remain server-managed.

## Browser limitations

- PWA install UX differs between Chrome Android, Samsung Internet and Safari iOS.
- iOS may not expose the Chromium `beforeinstallprompt` API; the portal does not show an install button.
- Camera capture behaviour is controlled by mobile browser/OS file picker.
