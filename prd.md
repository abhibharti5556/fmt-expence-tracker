# Product Requirements Document — Final Mile Techies Expense Management System

> **Revision note (2026-09-20):** This is a reviewed and upgraded version of
> the original PRD. Content is unchanged except where marked **[UPDATED]**
> or **[NEW]**. See `memory.md` for the full review log and `task.md` for
> the reprioritized backlog that came out of this review.

## 1. Overview

An internal web application for **Final Mile Techies** (a logistics and
warehousing company) that lets Admin fund employees with a spendable
balance, lets employees log logistics/warehousing expenses against that
balance with UPI payment proof, and gives Admin full visibility and Excel
reporting over all money movement.

The system replaces informal (spreadsheet/WhatsApp) tracking of who was
given how much money and what they spent it on, with a single auditable
record per expense: employee, amount, purpose, invoice, and payment
confirmation.

## 2. Users & Roles

| Role | Identity | Access |
|---|---|---|
| **Admin** | Single account, credentials from `.env` (`ADMIN_USERNAME` / `ADMIN_PASSWORD`); not stored in the database | Full access: create/edit employees, add money, view/audit all expenses, analytics, Excel reports |
| **Employee** | Admin-created, permanent Employee ID (e.g. `EMP001`) + password | Self-service: view own balance/history, submit expenses, manage own profile/password |

There is no self-registration — Admin is the only entry point for creating
employee accounts. There is no multi-admin or approval-hierarchy role today
**[UPDATED — see §6 Non-Goals: this is now flagged as a likely near-term
need rather than a settled decision, given multi-location operations]**.

## 3. Core Concepts

- **Balance** — never stored directly; always computed as
  `total money credited by Admin − total submitted expenses`. This is the
  single source of truth used on every dashboard, form, and report.
- **Expense** — one of two types:
  - **Logistics** — requires a Docket Number.
  - **Warehousing** — requires a free-text reason.
- **Transaction ID** — auto-generated per expense: `EXP-YYYYMMDD-NNNN`,
  daily-resetting sequence.
- **Payment proof** — every expense submission requires an invoice/supporting
  document AND a UPI payment screenshot + reference number before it is
  recorded.

## 4. Key User Flows

### 4.1 Admin: fund an employee
1. Admin creates an Employee (name, Employee ID, mobile, email, password,
   optional opening balance).
2. Admin adds money to an employee at any time (amount, purpose, remarks,
   date) — recorded as a `MoneyTransaction` (CREDIT).
3. Employee's balance updates immediately (derived, not stored).

### 4.2 Employee: submit an expense
1. Employee chooses expense type — Logistics or Warehousing.
2. Fills type-specific details + uploads an invoice/supporting document.
3. Reviews the draft; sees current balance and whether the amount is covered.
4. Initiates payment via UPI deep link to the company UPI ID (or pays
   manually), since the app cannot detect payment completion automatically.
5. Confirms payment by entering the UPI reference number and uploading a
   payment screenshot.
6. Expense is recorded (`payment_status = SUBMITTED`) and now counts against
   the employee's balance; a success screen shows the transaction ID.
   **[UPDATED — the balance check in steps 3–6 must be re-verified inside
   the same database transaction that writes the final expense row, not
   just re-queried beforehand. See `rules.md` §1 and `architecture.md` §7.]**

### 4.3 Admin: audit & report
- Browse/search/filter all expenses (date range, employee, type, status,
  free-text search across transaction ID, employee, docket no., UPI ref).
- Open any expense to see full detail: employee info, expense info, payment
  info, invoice, and payment screenshot.
- View employee-wise analytics (daily spend trend, logistics vs
  warehousing split) and a company-wide dashboard (KPIs, 14-day and 6-month
  trend charts, top spenders).
- Download filtered **Expense Report** (Summary + Transactions sheets) or
  the **Money Distribution Report** (every credit given to employees) as
  formatted Excel files.

## 5. Functional Requirements (implemented)

- Role-based login (Admin vs Employee), session-based auth, CSRF protection.
- Admin: create/edit employees, reset employee password, activate/deactivate
  employees (soft — inactive employees can't log in), add money.
- Employee: submit Logistics or Warehousing expense with invoice upload,
  UPI payment initiation, payment confirmation with screenshot + reference.
- Balance is always derived, never manually editable, and enforced at
  submission time (expense amount cannot exceed current balance).
- File uploads validated by extension **and** content (Pillow image
  verification for images, PDF magic-byte check for PDFs); stored under
  generated non-guessable filenames outside `static/`, served only through
  authenticated routes.
- Excel exports (pandas + openpyxl) respecting the active Reports filters.
- Pagination, search, and filtering on both Admin and Employee expense
  lists.
- Profile management (name/mobile/email/photo, password change) for
  employees; read-only profile view for Admin.

## 6. Non-Goals / Out of Scope (current version)

- No expense approval/rejection workflow — every correctly-submitted
  expense is immediately final (`payment_status` is always `SUBMITTED`
  today; the field is designed to support future statuses like
  `VERIFIED`/`REJECTED` without a migration, but nothing writes them yet).
  **[UPDATED — for an app that gates real money movement, treat this as
  the highest-priority "likely ask" in `task.md`, not a settled non-goal.]**
- No automatic UPI payment verification — completion is self-reported by
  the employee.
- No email/SMS notifications.
- No multi-admin accounts, roles/permissions beyond Admin/Employee, or
  audit log of Admin actions. **[UPDATED — the missing admin audit log is
  now called out as a security gap in `rules.md` §8, not just a feature gap.]**
- No mobile app — responsive web only.

## 7. Success Criteria

- Admin can, without leaving the app, answer "how much have we given X,
  how much have they spent, and on what" for any employee at any time.
- Every expense has traceable proof (invoice + payment screenshot +
  reference number) reachable from the admin audit view.
- Monthly closing/reporting is a filtered Excel download, not manual
  spreadsheet reconciliation.
- **[NEW]** No two concurrent expense submissions can ever cause an
  employee's balance to go negative, even under production-scale
  concurrent load (see `rules.md` §1 and `architecture.md` §7).
- **[NEW]** Every admin-initiated change to money or employee records is
  traceable to that admin, with a timestamp (see `rules.md` §8).