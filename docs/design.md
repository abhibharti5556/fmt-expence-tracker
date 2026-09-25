# Design System — Final Mile Techies Expense Management System

> **Revision note (2026-09-20):** Reviewed — no problems found in this
> file. Content is unchanged from the original; kept here so the full doc
> set stays together as one current package. See `memory.md` for the
> review log covering all six files.

## 1. Foundations (`static/css/style.css`)

### Color tokens

| Token | Value | Use |
|---|---|---|
| `--color-bg` | `#F6F7F9` | Page background |
| `--color-surface` | `#FFFFFF` | Cards, panels |
| `--color-surface-alt` | `#F9FAFB` | Secondary surfaces (table stripes etc.) |
| `--color-border` / `--color-border-strong` | `#E4E7EC` / `#D3D8E0` | Dividers, input borders |
| `--color-text` | `#1E2127` | Primary text |
| `--color-text-secondary` | `#5B6472` | Secondary text |
| `--color-text-muted` | `#8A93A2` | Placeholder / hint text |
| `--color-navy` / `-light` / `-border` | `#1B2130` / `#262E42` / `#333B4F` | Admin sidebar / dark surfaces |
| `--color-brand` | `#F2A61D` (amber) | Primary brand accent — CTAs, active states |
| `--color-brand-dark` / `-soft` / `-text` | `#D68F0E` / `#FDF1DC` / `#8A5A00` | Brand hover/pressed, soft badge bg, badge text |
| `--color-success` / `-soft` | `#1D8A5E` / `#E7F6EF` | Positive states (credit, submitted) |
| `--color-warning` / `-soft` | `#B7791F` / `#FBF0DD` | Caution states |
| `--color-error` / `-soft` | `#DC2626` / `#FDEDED` | Errors, insufficient balance |
| `--color-info` / `-soft` | `#2563EB` / `#EAF1FE` | Informational flashes |

### Typography

- **Display font**: `Lexend` — headings, KPI numbers, nav labels.
- **Body font**: `Source Sans 3` — body copy, form fields, table content.
- Both loaded from Google Fonts; fallback to system sans-serif stack.

### Spacing, radius, shadow scale

- Spacing: `--space-1` (4px) through `--space-8` (64px), 4/8px rhythm.
- Radius: `--radius-sm` 6px (inputs/badges), `--radius-md` 10px (cards),
  `--radius-lg` 16px (modals/panels), `--radius-pill` (chips/status pills).
- Shadow: `--shadow-sm/md/lg` — soft, low-opacity navy shadows
  (`rgba(16,24,40,…)`), used for card elevation and dropdowns.

## 2. Layout System

- `templates/base.html` — root HTML shell: fonts, CSS/JS includes, flash
  message partial, `{% block content %}`.
- `templates/layout_admin.html` — Admin shell: **dark navy sidebar**
  (`sidebar_admin.html`) + top bar + content area. Sidebar nav: Dashboard,
  Employees, Add Money, Expenses, Analytics, Reports, Profile.
- `templates/layout_employee.html` — Employee shell: sidebar
  (`sidebar_employee.html`) showing live balance, nav: Dashboard, New
  Expense, My Expenses, Profile.
- `templates/partials/` — reusable fragments:
  - `flash_messages.html` — role-colored flash banners (success/error/info)
    mapped to the semantic color tokens above.
  - `macros.html` — shared Jinja macros (form fields, buttons, badges).
  - `step_indicator.html` — progress stepper for the expense wizard.
  - `sidebar_admin.html` / `sidebar_employee.html`.

Bootstrap 5 is used for grid/utility classes and base component behavior
(modals, dropdowns); visual identity is overridden by the custom token
system in `style.css` rather than default Bootstrap theming.

## 3. Key Screens & Flows

### Admin
- **Dashboard** — KPI cards (distributed, spent, logistics/warehousing
  split, available balance, active employees, today's spend) + Chart.js
  visuals: 14-day daily trend, 6-month monthly trend, top-10
  employee-wise spend.
- **Employees** — searchable list with per-row computed totals
  (received/spent/balance); Add/Edit forms; per-employee detail page
  (full transaction + expense history, invoice/screenshot access).
- **Add Money** — form + a running list of the 25 most recent credits.
- **Expenses** — filterable/paginated audit table (date range, employee,
  type, status, free-text search) → detail view with invoice + payment
  screenshot inline.
- **Analytics** — per-employee drill-down (daily trend, type split) or,
  with no employee selected, a company-wide ranked list of spenders.
- **Reports** — same filter UI as Expenses, with a live preview (first 50
  rows) and two Excel download buttons.

### Employee
- **Dashboard** — balance + received/spent summary, recent expenses.
- **New Expense wizard** (session-backed, linear, back-navigable via the
  step indicator):
  1. Choose type (Logistics / Warehousing)
  2. Type-specific form + invoice upload
  3. Review (amount vs. balance, insufficient-balance warning)
  4. Pay — UPI deep link button to the company UPI ID
  5. Confirm — enter UPI reference number + upload payment screenshot
  6. Success — shows the generated transaction ID
- **My Expenses** — own filtered/paginated history + detail view.
- **Profile** — edit name/mobile/email/photo, change password.

### Shared
- **Auth**: role-select screen → separate Admin login / Employee login
  forms.
- **Errors**: branded 403/404/500 pages (not framework defaults).

## 4. Component Conventions

- **Status/type badges**: pill-shaped, colored via the semantic soft/text
  token pairs (e.g. success-soft bg + success text for "Active"/
  "Logistics"; error-soft/error for rejected states — reserved for future
  use since only `SUBMITTED` exists today).
- **KPI cards**: display-font numeric value, secondary-text label, brand
  or semantic-colored icon (Phosphor Icons via CDN).
- **Currency**: always rendered via the `inr` Jinja filter
  (`utils/helpers.py: format_inr`) — Indian digit grouping
  (`₹12,34,567.00`), never raw floats.
- **Forms**: server-rendered, re-populated with submitted values on
  validation error (`form=form` passed back into the same template) so
  employees/admins never lose input on a failed submit.
- **Charts**: Chart.js via CDN, one canvas per chart, data passed in as
  Jinja-rendered JSON arrays from the route (no client-side data fetching
  — everything is server-computed and injected at render time).

## 5. Responsiveness

- Bootstrap grid breakpoints drive layout collapse (sidebar → off-canvas
  on small screens, tables → horizontally scrollable).
- No dedicated mobile app; the web UI is the only interface for both
  roles, so form-heavy screens (expense wizard, employee forms) are
  designed to remain usable at phone width.

## 6. Branding

- Company logo: `static/images/final-mile-techies-logo.png`, used in the
  sidebar header and login screens.
- `company_name` is injected globally via the `context_processor` in
  `app.py` from `Config.COMPANY_NAME`, so all templates reference it
  rather than hardcoding "Final Mile Techies".