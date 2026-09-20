# Business & Validation Rules — Final Mile Techies Expense Management System

> **Revision note (2026-09-20):** Reviewed and upgraded. §1 and §2 have
> targeted additions; **§8 is entirely new** (security/integrity rules
> that weren't documented anywhere before). See `memory.md` for the
> review log.

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
- **[NEW — recommended]** The final balance check in `expense_confirm`
  must happen **inside the same database transaction** as the `Expense`
  insert, not as a separate query beforehand. Today this is a read-then-
  write with a gap in between; it is only safe because the current dev
  server is single-process. Before running under multiple workers/threads,
  this must become one atomic operation (see `architecture.md` §7).

## 2. Identity & Auth

- **Admin** is a single, env-configured identity
  (`ADMIN_USERNAME`/`ADMIN_PASSWORD`) — not a database row. Compared with
  `secrets.compare_digest` (constant-time) on every login.
- **Employee ID** format: 3–20 characters, letters/numbers/hyphens only
  (`EMPLOYEE_ID_RE = ^[A-Za-z0-9\-]{3,20}$`), must be unique, always
  upper-cased on creation (`routes/admin.py: add_employee`).
- **Password** minimum length: 6 characters, for both employee creation
  and password reset/change (`routes/admin.py`, `routes/employee.py`).
  **[NEW — recommended]** 6 characters with no complexity requirement is
  weak for an app that gates money movement. Recommend raising the
  minimum to 8+ characters and requiring at least one letter and one
  digit.
- **Mobile**: `^\+?\d{10,15}$`. **Email**: simple `local@domain.tld` regex
  (not full RFC 5322) — both enforced on employee create/edit and
  employee's own profile edit.
- Inactive employees (`status = "Inactive"`) cannot log in, and an
  already-logged-in employee is force-logged-out the moment their status
  flips to Inactive (checked on every request via `employee_required`).
- Session is cleared (`session.clear()`) on every login and logout — no
  role/session bleed-over between Admin and Employee.
- **[NEW — recommended]** No session lifetime is currently configured —
  a session cookie is valid until the browser clears it. Set
  `PERMANENT_SESSION_LIFETIME` (e.g. 8–12 hours) and mark sessions
  non-permanent by default so idle sessions expire.

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
- **[NEW — recommended]** `docket_no` has no uniqueness constraint today,
  so the same docket number can be logged more than once. Recommend a
  unique index on `docket_no` (nullable-safe, since Warehousing expenses
  have none) so a duplicate is caught at submission time rather than
  discovered during an audit.

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

## 8. Security & Audit — [NEW section]

None of the following exist in the code yet. They're captured here as
rules to implement (in priority order for an app that moves real money),
mirroring `architecture.md` §5 and `task.md`.

1. **[recommended] Login rate-limiting / lockout.** Neither the Admin nor
   the Employee login route currently limits repeated failed attempts.
   Add a per-identity (and per-IP) attempt counter with a temporary
   lockout or increasing delay after, e.g., 5 failed attempts in 10
   minutes.
2. **[recommended] Admin action audit log.** Today only money credits
   record `created_by`. Extend this pattern to employee create/edit,
   password resets, and activate/deactivate actions — a simple
   `AdminAuditLog(admin_username, action, target_user_id, timestamp,
   detail)` table is enough; no UI is required initially, just the
   record.
3. **[recommended] Session hardening.** `PERMANENT_SESSION_LIFETIME` set
   explicitly; `SESSION_COOKIE_HTTPONLY=True`; `SESSION_COOKIE_SECURE=True`
   once served over HTTPS; `SESSION_COOKIE_SAMESITE="Lax"`.
4. **[recommended] Balance-check atomicity.** See §1 — must be fixed
   before running under any multi-worker production server.