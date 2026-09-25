# Business & Validation Rules — Final Mile Techies Expense Management System

> **Revision note (2026-09-20):** Reviewed and upgraded. §1 and §2 have
> targeted additions; **§8 is entirely new** (security/integrity rules
> that weren't documented anywhere before). See `memory.md` for the
> review log.
>
> **Update (2026-09-20, later):** Most items below marked
> **[recommended]** are now implemented — see the inline "✅ implemented"
> notes and `memory.md`'s "Implementation pass" entry for what changed
> and where.

Source of truth for every rule is the code cited in parentheses. If this
file and the code disagree, the code wins — update this file to match.
For rules marked **[recommended]**, the code does not yet implement this —
treat it as a rule to implement, not a description of current behavior.

## 1. Balance

- Balance is **always derived**, never stored or manually editable:
  `balance = total CREDIT MoneyTransactions − total Expenses with
  payment_status in BALANCE_COUNTING_STATUSES` (`utils/helpers.py`).
- An expense **cannot** be submitted for more than the employee's current
  balance. Checked at review, at the pay step, and again at final confirm
  (server-side, re-checked each time in case balance changed mid-wizard)
  (`routes/employee.py: expense_review/expense_pay/expense_confirm`).
- Only `payment_status == "SUBMITTED"` counts toward balance today
  (`BALANCE_COUNTING_STATUSES = ("SUBMITTED",)`). If future statuses like
  `VERIFIED`/`REJECTED` are added, this tuple is the single place that
  decides what still counts.
- **✅ implemented (2026-09-20).** The balance check and the `Expense`
  insert are now effectively atomic: `app.py` forces every SQLite
  transaction to take the write lock (`BEGIN IMMEDIATE`) at its first
  statement, not at first write, so no second request can read a stale
  balance while this one is mid-submission. See `architecture.md` §7.

## 2. Identity & Auth

- **Admin** is a single, env-configured identity
  (`ADMIN_USERNAME`/`ADMIN_PASSWORD`) — not a database row. Compared with
  `secrets.compare_digest` (constant-time) on every login.
- **Employee ID** format: 3–20 characters, letters/numbers/hyphens only
  (`EMPLOYEE_ID_RE = ^[A-Za-z0-9\-]{3,20}$`), must be unique, always
  upper-cased on creation (`routes/admin.py: add_employee`).
- **Password** minimum length: 6 characters, for both employee creation
  and password reset/change (`routes/admin.py`, `routes/employee.py`).
  **[recommended, not yet implemented]** 6 characters with no complexity
  requirement is weak for an app that gates money movement. Recommend
  raising the minimum to 8+ characters and requiring at least one letter
  and one digit — tracked in `task.md`.
- **Mobile**: `^\+?\d{10,15}$`. **Email**: simple `local@domain.tld` regex
  (not full RFC 5322) — both enforced on employee create/edit and
  employee's own profile edit.
- Inactive employees (`status = "Inactive"`) cannot log in, and an
  already-logged-in employee is force-logged-out the moment their status
  flips to Inactive (checked on every request via `employee_required`).
- Session is cleared (`session.clear()`) on every login and logout — no
  role/session bleed-over between Admin and Employee.
- **✅ implemented (2026-09-20).** `PERMANENT_SESSION_LIFETIME` defaults
  to 8 hours (env-configurable via `SESSION_LIFETIME_HOURS`);
  `session.permanent = True` is set on every successful login.

## 3. Expenses

- Two types only: **Logistics** (requires Docket Number) and
  **Warehousing** (requires a free-text Reason). Both require: amount
  (> ₹0), Purpose, Approved By, and an invoice/supporting document.
- `transaction_id` format: `EXP-YYYYMMDD-NNNN`, sequence resets daily,
  generated server-side and guaranteed unique via retry-on-collision
  (`utils/helpers.py: generate_transaction_id`) — never client-supplied.
- Every expense requires, before it is recorded:
  1. An invoice/supporting document (validated — see File Uploads).
  2. A UPI reference number, minimum 4 characters.
  3. A payment screenshot (validated — see File Uploads).
- The expense submission wizard is entirely session-based
  (`session["expense_draft"]`) — nothing is written to the `expenses`
  table until the final confirm step. Abandoning the wizard at any
  earlier step leaves no expense record (but does leave the already-
  uploaded invoice file on disk — see `task.md`).
- **✅ implemented (2026-09-20), partially.** Submitting a Logistics
  expense with a Docket Number that already exists (case-insensitive) is
  now blocked with an error naming the earlier transaction
  (`routes/employee.py: expense_logistics`). This is an app-level check,
  not a DB constraint — a genuine unique index still requires
  Flask-Migrate (not yet adopted; see `task.md`) to apply safely to the
  existing database.

## 4. Money Transactions (Admin → Employee)

- Amount must be > ₹0; Purpose is required.
- Every credit is attributed: `created_by` stores the acting Admin's
  username (from session, falling back to configured `ADMIN_USERNAME`).
- An employee's opening balance at account creation is recorded as a
  normal `MoneyTransaction` (`purpose="Initial Balance"`), not a special
  field on `User` — it is fully visible in the employee's transaction
  history and the Money Distribution report.

## 5. File Uploads

| Upload | Allowed types | Max size | Extra validation |
|---|---|---|---|
| Profile photo | jpg, jpeg, png, webp | 5 MB | Pillow `Image.verify()` |
| Invoice / supporting doc | pdf, jpg, jpeg, png | 10 MB | PDF: `%PDF-` magic bytes; image: Pillow verify |
| Payment screenshot | jpg, jpeg, png | 5 MB | Pillow `Image.verify()` |

- Global hard cap on any request body: 12 MB (`MAX_CONTENT_LENGTH`).
- Every upload is renamed to a generated `uuid4`-based filename on save —
  the original filename is never trusted or persisted.
- Uploaded files are stored **outside** `static/` and are only ever
  served through an authenticated Flask route — an admin route checks
  `@admin_required`; an employee route additionally checks the requesting
  employee owns the expense (`expense.user_id == current_employee().id`,
  else `403`).

## 6. Access Control

- Every non-auth route is gated by one of `login_required`,
  `admin_required`, or `employee_required` — there are no unauthenticated
  data routes other than the login pages and static assets.
- Admin-only: employee management, add money, all-expenses view, company
  analytics/reports, Excel exports.
- Employee-only: own dashboard/profile/expense history/expense
  submission — never another employee's data (enforced per-route, not
  just per-template).

## 7. Reports

- Excel exports (`Expense Report`, `Money Distribution Report`) always
  reflect exactly the filters currently applied on the Reports screen —
  same query function, no separate "export all" path that could diverge
  from what's on screen.

## 8. Security & Audit

Originally captured as a set of gaps; most are now implemented
(2026-09-20). Mirrors `architecture.md` §5 and `task.md`.

1. **✅ implemented — Login rate-limiting / lockout.**
   `utils/rate_limit.py`: 5 failed attempts (configurable) within a
   10-minute window locks that identity+IP out for 15 minutes. In-memory
   — resets on process restart, and is per-process (not shared) if the
   app ever runs under multiple worker processes. Verified against the
   live dev server: 5 wrong-password POSTs to `/login/admin` trigger the
   lockout message; a 6th is still blocked.
2. **✅ implemented — Admin action audit log.** `models/audit.py:
   AdminAuditLog` + `log_admin_action()`, called from
   `routes/admin.py` on employee create/edit/password-reset/
   status-toggle. Money credits still use the pre-existing `created_by`
   field on `MoneyTransaction` rather than duplicating into this table.
   No UI yet — query `admin_audit_log` directly (e.g. via a SQLite
   browser) until one is built.
3. **✅ implemented — Session hardening.** See §2 above and `config.py`.
4. **✅ implemented — Balance-check atomicity.** See §1 above and
   `architecture.md` §7.