# IBB Portal Screen Sketches

## Source Assets

The reference assets are stored in `../assets/`:

- `public-login-landing.png`: public landing and login.
- `client-dashboard.png`: authenticated client admin dashboard.
- `partner-dashboard.png`: partner dashboard and client management.
- `policies-list-details.png`: policies list, filters, detail drawer, mobile sheet.
- `new-application-flow.png`: new insurance application wizard.

## Global Visual System

- Brand: IBB logo at top left; gold globe mark with gold `IBB` wordmark.
- Palette: white background, off-white section bands, deep navy text/CTA, gold accent lines/icons, pale blue selected rows/cards, green success chips, amber warning chips, red duplicate/error chips.
- Typography: large serif page headings; sans-serif UI labels, table text, controls, and navigation. Headings should feel editorial and premium, but dense operational areas should stay compact.
- Layout: max-width desktop shell, generous top sections, structured grids, thin borders, subtle shadows. Avoid nested cards.
- Decoration: use a very light global map/network motif only in hero/dashboard backgrounds. Keep it low contrast and never behind critical text.
- Icons: line icons for products/status/actions. Prefer existing icon library equivalents.
- Controls: primary buttons navy filled; secondary buttons navy outline; icon buttons for view, menu, download, close, sort, calendar, notifications.
- Radius: mostly 8px for cards, tables, inputs, buttons, drawers, and mobile cards.
- Data density: dashboards and tables are operational, not marketing-heavy. Keep content scannable and repeat-use friendly.

## Navigation Patterns

Public header:

- Logo left.
- Desktop nav: Products, Industries, Partners, Resources, About IBB, Login.
- Mobile: logo and menu icon.

Authenticated client header:

- Logo left.
- Company selector centered/right.
- Notifications with badge.
- User avatar/name/role menu.
- Mobile: logo, notification, menu.

Partner header:

- Logo left, `Partner portal` label.
- Notifications and partner/user menu.
- Mobile: logo and menu icon.

Footer:

- Logo, About IBB, Careers or Resources, Compliance or Support, Privacy Policy, Terms of Use, copyright.
- Keep footer slim; do not overbuild marketing content.

Mobile authenticated navigation:

- Bottom tab bar for primary areas.
- Client tabs: Home, Applications, Policies, Documents, Profile.
- Partner tabs: Dashboard, Clients, Applications, Profile.
- Policies screen can use a central plus/create action when the workflow needs it.

## Public Landing And Login

Purpose: entry page for companies, carriers, and partners.

Hero content:

- H1: `International insurance portal for companies, carriers, and partners`.
- Supporting text: manage applications, policies, documents, statuses, and renewals in one secure place; global reach, local expertise, trusted outcomes.
- CTAs: `Log in`, `Request access`.
- Desktop includes a login card in the hero; mobile stacks hero CTAs and login card.

Login card:

- Title: `Log in to your account`.
- Fields: Email address, Password.
- Password visibility toggle.
- Forgot password link.
- Primary button: `Log in`.
- Reassurance: secure/encrypted/protected message.

Product cards:

- Auto Insurance.
- Cargo Insurance.
- Liability Insurance.
- Property Insurance.
- Medical Insurance.

How it works:

1. Application: submit details online.
2. Review: experts review and assess needs.
3. Policy issuance: receive tailored coverage.
4. Documents: access documents anytime.

Trust section:

- Global expertise.
- A-rated partners.
- Secure & compliant.
- Service you can count on.

Final CTA:

- `Ready to streamline your insurance operations?`
- Buttons: `Log in`, `Request access`.

## Client Dashboard

Purpose: authenticated client overview for insurance program activity.

Hero:

- Greeting: `Welcome back, {first_name}`.
- Subtitle: `Here's what's happening with your insurance program today.`
- Primary CTA: `Create application`.
- Background: faint globe/network motif.

Metric cards:

- Active policies.
- Applications in progress.
- Expiring soon.
- Awaiting approval.

Main sections:

- Recent applications: application ID, title/product, type icon, submitted date, status chip, `View all`.
- Expiring policies: policy name, policy ID, expiration in days, `Renew`.
- Recent documents: document title, reference ID, file type, date, download icon.
- Quick actions: Create application, Upload documents, Request certificate, Report a claim, Contact your broker.
- Support band: `Need help?` and `Contact us`.

Status chips:

- `Under review`: blue.
- `Awaiting documents`: amber.
- `Issued`: green.

Mobile:

- Metric cards become a 2-column grid.
- Tables become stacked cards.
- Keep primary CTA above metrics.

## Partner Dashboard

Purpose: partner manages only clients they created and related applications.

Hero:

- Label: `Partner portal`.
- Greeting: `Welcome back, Partner`.
- Subtitle: manage clients created by the partner and their insurance applications.
- Permission note: partner can only view/manage clients they created.
- CTAs: `Create client`, `Create application`.

Metric cards:

- My clients.
- Clients awaiting approval.
- Open applications.
- Issued policies.

Client list:

- Search by company or contact.
- Filter button.
- Desktop table columns: Company name, Primary contact, Date created, Status, Actions.
- Actions: view, overflow menu.
- Mobile cards show company, short ID, status chip, overflow menu.

Partner client statuses:

- `Awaiting verification`: amber.
- `Confirmed`: green.
- `Duplicate found`: red.
- `Needs clarification`: blue.

Related applications panel:

- Selected client summary.
- Totals: total applications, open, submitted, issued.
- CTA: `Create application`.
- Table/card fields: Application ID, Product type, Date created, Status, Last updated, Actions.

Demo client rows from sketches are placeholders only:

- Oceanic Shipping Ltd.
- Bluewave Logistics LLC.
- Global Trade Solutions.
- Summit Retail Group.
- Arcadia Manufacturing.
- Greenfield Energy Ltd.
- Northbridge Imports.
- Helix Construction Co.

## Policies List And Details

Purpose: policy management and renewal/request actions.

Header:

- Title: `Policies`.
- Subtitle: view and manage insurance policies in one place.
- Desktop export button top right; mobile export button near list bottom.

Search and filters:

- Search by policy number, vehicle number, or VIN.
- Filter button with active count.
- Clear all.
- Filters: Product, Company, Status, Expiry date, Insured object.
- Sort by `Valid to (soonest)`.

Desktop list:

- Use selectable rows with checkbox.
- Columns: Policy number, Product, Company, Insured object, Valid from, Valid to, Status, Actions.
- Selected row has blue border and subtle selected background.

Detail drawer:

- Opens on desktop as right side panel.
- Mobile uses a bottom sheet.
- Contains product icon, policy number, internal policy reference, status chip, copy icon, close action.
- Primary action: `View policy`.
- Secondary action: `Request renewal`.
- Information groups: policy information, policy period, coverage summary, related documents, support.

Policy statuses:

- `Active`: green.
- `Expiring soon`: amber.
- `Archived`: neutral gray.

Demo policy products:

- Auto Insurance.
- Cargo Insurance.
- Liability Insurance.
- Property Insurance.
- Medical Insurance.

## New Application Flow

Purpose: step-by-step application creation with autosave and support.

Header:

- Public-like header for unauthenticated/request-access flows, or authenticated shell when launched inside portal.
- Breadcrumb: Home / New application.
- Title: `New insurance application`.
- Subtitle: start application in a few simple steps.

Application summary:

- Progress percent.
- Horizontal progress bar.
- Draft saved state and timestamp.

Product choice:

- Product cards with icon, title, short description, radio selection.
- Initial products shown: Auto Insurance and Cargo Insurance.

Stepper:

1. Product.
2. Company.
3. Insured Object.
4. Route / Details.
5. Documents.
6. Review.

Form card:

- Product-specific title and icon.
- Step count, e.g. `Step 1 of 6`.
- Field groups with required markers.
- Auto example fields: vehicle registration number, VIN/chassis number, country of registration, vehicle usage, start date, end date.
- Actions: `Save draft`, `Continue`.

Right rail:

- Your application summary with selected product and step statuses.
- Need help card with contact support.

Mobile:

- Summary, product choices, stepper, form, and right-rail summary stack vertically.
- Keep `Continue` reachable at the end of the visible form; avoid sticky controls unless tested for overlap.

Trust band:

- Global expertise.
- Secure & compliant.
- Trusted by partners.
- End-to-end support.

## Content Normalization

Use these corrected/normalized terms in implementation:

- `Log in` for the action; avoid mixed `Login`/`Log in` unless used as a noun.
- `Application` for insurance submissions; avoid `claim` unless it is a real claim workflow.
- `Policy` for issued insurance contracts.
- `Document` for downloadable policy files, certificates, invoices, wording, schedules.
- `Partner` users can create/manage their own clients, but cannot see all portal clients.
- `Client Admin`, `Client Executor`, and `Client Viewer` are role labels; use backend role codes for logic.

## Implementation Notes

- Keep frontend demo data in local constants, fixtures, Storybook stories, or mocked API handlers.
- Do not create database tables for sketch-only companies, contacts, policies, or documents.
- Do not put emails, contact names, vehicle numbers, VINs, document names, or Bitrix payloads into technical logs.
- If implementing real data, map to backend/API fields and Bitrix24 IDs rather than copying sketch strings.
- Add empty, loading, error, and permission-denied states for every list/detail flow.
- Verify desktop and mobile with screenshots before finishing significant UI work.
