# Architecture — Final Mile Techies Expense Management System

> **Revision note (2026-09-20):** Reviewed and upgraded. Unchanged sections
> are preserved as-is; new/changed material is marked **[UPDATED]** or
> **[NEW]**. See `memory.md` for the review log.

## 1. Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python, Flask 3.0 |
| ORM / DB | Flask-SQLAlchemy, SQLite (`instance/expenses.db`) |
| Forms / CSRF | Flask-WTF (`CSRFProtect`) |
| Auth | Server-side session (Flask `session`), Werkzeug password hashing |
| Frontend | Jinja2 templates, Bootstrap 5, vanilla JS, Chart.js (CDN), Phosphor Icons (CDN) |
| Reports | pandas + openpyxl (in-memory `.xlsx` generation, no temp files) |
| Images | Pillow (upload content validation) |
| Config | `python-dotenv` (`.env`) |
| **[NEW] Migrations** | Still not present — **Alembic (via `Flask-Migrate`) is recommended before the schema grows further.** Deliberately deferred (2026-09-20 pass): adopting it means running `flask db stamp head` against the real `instance/expenses.db`, which should happen with the user present. See §2.2. |
| **[NEW] Production server** | `wsgi.py` + `waitress` (Windows) / `gunicorn` (Linux) are now wired up and documented in README — **but nothing is actually deployed behind Nginx/systemd/TLS yet.** That remaining step is infra, not code. |

No frontend build step, no JS framework — schema is currently created via
`db.create_all()` on startup (see §8 for why this should change soon).

## 2. Application Structure

### 2.1 Current structure (as implemented, 2026-09-21)

```
final-mile-techies/
├── app.py                  App factory (create_app), blueprint registration,
│                           error handlers, jinja filters, SQLite locking setup
├── wsgi.py                 Production entrypoint (`from app import create_app;
│                           app = create_app()`) — what waitress/gunicorn point at
├── config.py                Config class — env-driven settings
├── extensions.py             Shared, uninitialized extension instances (db, csrf)
├── requirements.txt          Pinned runtime dependencies
├── requirements-dev.txt       requirements.txt + pytest
├── .env / .env.example        Real config (gitignored) / committed template
├── .gitignore
├── README.md                  Setup, run (dev + production), test, maintenance
│
├── docs/                      All planning/reference docs (this file included)
│   ├── prd.md                  Product scope, roles, flows, non-goals
│   ├── architecture.md          This file
│   ├── rules.md                  Business & validation rules
│   ├── design.md                  Design tokens, layout, component conventions
│   ├── task.md                     Done/open work, prioritized
│   └── memory.md                    Decision log — the "why" behind non-obvious choices
│
├── models/
│   ├── __init__.py            Re-exports models + status/type constants
│   ├── models.py                User, MoneyTransaction, Expense
│   └── audit.py                  AdminAuditLog + log_admin_action()
│
├── routes/
│   ├── __init__.py
│   ├── auth.py                  /, /login, /login/admin, /login/employee,
│   │                            /logout, profile-image serving, login lockout
│   ├── admin.py                   /admin/* — dashboard, employees, add-money,
│   │                              expenses, analytics, reports, audit logging
│   └── employee.py                 /employee/* — dashboard, profile, expense
│                                   submission wizard, own expense history
│
├── utils/
│   ├── __init__.py
│   ├── decorators.py            login_required / admin_required / employee_required
│   ├── helpers.py                 Balance calc, transaction ID gen, file validation/
│   │                              storage, INR formatting
│   ├── upi.py                      UPI deep-link builder
│   ├── excel_reports.py             openpyxl report builders
│   └── rate_limit.py                 In-memory failed-login tracker/lockout
│
├── scripts/
│   └── cleanup_orphaned_uploads.py   Maintenance sweep for orphaned uploads
│
├── tests/                      pytest suite — balance math, transaction ID
│   ├── conftest.py             collision handling, upload content validation.
│   ├── test_balance.py         Runs against an isolated temp DB, never touches
│   ├── test_transaction_id.py  instance/expenses.db.
│   └── test_uploads.py
│
├── templates/                 Jinja2 templates, split by role (admin/, employee/,
│                              auth/, errors/, partials/) — see design.md §2
├── static/                    CSS, JS, logo — never used for uploaded content
│
├── uploads/                    Runtime-created, outside static/:
│                               profile_images/, invoices/, payment_screenshots/
└── instance/                   Runtime-created; holds expenses.db (SQLite)
```

Not present yet, and deliberately so — see `task.md`:
- **`migrations/`** (Flask-Migrate/Alembic) — adopting it means running
  `flask db stamp head` against the real `instance/expenses.db`, which
  should happen with the user present, not unattended. §2.2 has the
  order to follow when ready.
- **`logs/`** — only needed once file-based production logging is added;
  not required for the current single-process dev/small-scale use.

### 2.2 Adopting Flask-Migrate, when ready

1. `pip install Flask-Migrate`, wire `Migrate(app, db)` into `extensions.py`.
2. `flask db init`.
3. `flask db stamp head` against the *existing* database — tells Alembic
   "this schema already matches this migration state" without trying to
   recreate it.
4. From this point on, schema changes go through `flask db migrate` +
   `flask db upgrade` instead of relying on `db.create_all()`.
5. Once in place, promote the app-level Docket Number duplicate check
   (`rules.md` §3) to a real DB unique constraint via a migration.

## 3. Request Lifecycle

1. `create_app()` builds the Flask app, loads `Config`, ensures
   `instance/` and the three `uploads/` subfolders exist.
2. `db.init_app` / `csrf.init_app` wire up SQLAlchemy and CSRF protection.
3. Three blueprints are registered: `auth_bp` (no prefix), `admin_bp`
   (`/admin`), `employee_bp` (`/employee`).
4. A `context_processor` injects `company_name`, `current_year`,
   `session_role`, and (for logged-in employees) `sidebar_balance` into
   every template.
5. `db.create_all()` runs inside the app context at import time — the
   SQLite schema is created on first run automatically, no migration step.
6. Dev entrypoint: `python app.py` → `app.run(debug=Config.FLASK_DEBUG)`,
   binds `127.0.0.1:5000`.

## 4. Data Model

```
User (users)
  id, employee_id (unique), name, mobile, email, profile_image,
  password_hash, role ("EMPLOYEE"), status (Active/Inactive),
  created_at, updated_at
  1--* MoneyTransaction (user_id FK)
  1--* Expense (user_id FK)

MoneyTransaction (money_transactions)
  id, user_id FK, amount (Numeric 12,2), transaction_type ("CREDIT"),
  purpose, remarks, created_at, created_by
  -- always a credit today; transaction_type exists for future debit/
     adjustment types without a schema change

Expense (expenses)
  id, transaction_id (unique, "EXP-YYYYMMDD-NNNN"), user_id FK,
  expense_type ("LOGISTICS" | "WAREHOUSING"), amount (Numeric 12,2),
  docket_no (Logistics only), purpose, reason (Warehousing only),
  approved_by, remarks,
  upi_reference_no, payment_status ("SUBMITTED" today),
  invoice_file, payment_screenshot,
  created_at, updated_at
```

**✅ Partially implemented (2026-09-20).** `docket_no` still has no DB-level
uniqueness constraint, but `routes/employee.py: expense_logistics` now
blocks submission of a Docket Number that's already in use (case-
insensitive), naming the earlier transaction. A real unique index is
still the more robust fix — deferred until Flask-Migrate is adopted
(§2.2), since altering the existing `instance/expenses.db` safely needs
that tooling.

There is no Admin table — Admin identity is entirely env-config-based
(see `rules.md` §Auth).

### Balance — derived, not stored

```
balance(user) = SUM(MoneyTransaction.amount WHERE type=CREDIT)
              − SUM(Expense.amount WHERE payment_status IN BALANCE_COUNTING_STATUSES)
```

Computed live in `utils/helpers.py` (`get_employee_balance`,
`get_employee_totals`) — every dashboard, form, and report calls through
these functions rather than caching or storing a balance column. This
guarantees the balance can never drift from its ledger.

**✅ Fixed (2026-09-20).** The balance check during expense submission is
still logically read-then-write, but it's no longer unsafe: every DB
transaction now takes SQLite's write lock (`BEGIN IMMEDIATE`) at its
first statement rather than at first write (see §7), so a second request
can't read a stale balance while the first is mid-submission. This holds
even under a multi-worker production server, since SQLite's single-writer
lock is enforced at the file level, not per-process.

## 5. Security Architecture

- **CSRF**: global `CSRFProtect()` via Flask-WTF.
- **Passwords**: Werkzeug `generate_password_hash` / `check_password_hash`
  (salted, hashed — never stored/compared in plaintext).
- **Admin auth**: constant-time comparison (`secrets.compare_digest`)
  against `ADMIN_USERNAME`/`ADMIN_PASSWORD` env vars on every login; no
  Admin row in the DB, no Admin session persistence beyond the Flask
  session cookie.
- **Access control**: three decorators in `utils/decorators.py`
  (`login_required`, `admin_required`, `employee_required`) gate every
  route; `employee_required` additionally re-fetches the user from the DB
  on each request and rejects inactive accounts mid-session.
- **Ownership checks**: employee-facing expense/detail/file routes verify
  `expense.user_id == current_employee().id` and `abort(403)` otherwise —
  an employee cannot view another employee's expense by guessing an ID.
- **File storage**: uploads live outside `static/`, are renamed to a
  `uuid4`-based filename on save (original filename discarded), and are
  only ever served through authenticated Flask routes
  (`send_from_directory` behind `@admin_required`/`@employee_required`).
- **Upload validation**: extension allow-list + size cap + content
  verification (Pillow `Image.verify()` for images, `%PDF-` magic-byte
  check for PDFs) — rejects mislabeled files, not just wrong extensions.
- **Session**: server-side signed cookie (`SECRET_KEY`); `session.clear()`
  on every login/logout to prevent session fixation across roles.
  **✅ implemented (2026-09-20).** `PERMANENT_SESSION_LIFETIME` (default
  8h, env-configurable), `SESSION_COOKIE_HTTPONLY=True`,
  `SESSION_COOKIE_SAMESITE="Lax"`, `SESSION_COOKIE_SECURE` as an
  env-toggle for once the app is served over HTTPS.
- **✅ implemented (2026-09-20).** Login lockout on both the Admin and
  Employee login routes (`utils/rate_limit.py`) — 5 failed attempts in
  10 minutes locks that identity+IP out for 15 minutes, all
  configurable via env. In-memory/per-process — see `rules.md` §8.
- **✅ implemented (2026-09-20).** `AdminAuditLog` (`models/audit.py`)
  now records employee create/edit/password-reset/status-toggle with
  admin username, timestamp, and detail. See `rules.md` §8.

## 6. Reporting Pipeline

`utils/excel_reports.py` builds workbooks entirely in memory (`io.BytesIO`,
`openpyxl.Workbook`) — no temp files on disk:
- **Expense report**: Summary sheet (aggregate + employee-wise breakdown)
  + Transactions sheet (full detail, frozen header, autofilter, currency
  formatting), branded header styling.
- **Money Distribution report**: every credit transaction, filtered the
  same way as the Reports screen.

Both exports reuse the exact same filter query
(`_filter_expenses_query` in `routes/admin.py`) that powers the on-screen
Reports preview, so the download always matches what Admin sees.

## 7. Notable Design Decisions

- **No ORM-level enum for `payment_status`** — kept as a plain string
  column deliberately so future statuses (e.g. `VERIFIED`/`REJECTED`) can
  be introduced without a migration; `BALANCE_COUNTING_STATUSES` is the
  single tuple that decides what counts toward balance/KPIs/reports.
- **Expense submission is a session-backed multi-step wizard**
  (`session["expense_draft"]`): type → details+invoice → review → UPI pay
  → confirm+screenshot → success. Nothing is written to the DB until the
  final confirm step succeeds, so an abandoned wizard leaves no partial
  expense row. **✅ implemented (2026-09-20):** the invoice upload is no
  longer left orphaned either — `_discard_draft_invoice()` in
  `routes/employee.py` deletes it when the draft is abandoned
  (`expense_new`), overwritten (re-submitting a form), or the session
  ends (`routes/auth.py: logout`). `scripts/cleanup_orphaned_uploads.py`
  is the backstop for session-expiry cases (browser closed mid-wizard)
  those hooks can't catch.
- **Transaction ID generation retries on collision** rather than trusting
  a naive `count + 1`, to handle same-second concurrent submissions.
- **✅ implemented (2026-09-20) — Balance-check atomicity fix.** Rather
  than wrapping just the final insert, every SQLite transaction is now
  forced into `BEGIN IMMEDIATE` at the engine level
  (`app.py: _configure_sqlite_locking`), so the write lock is held from
  the balance check onward for the whole request. Simpler than manual
  per-route transaction management and closes the gap for every route
  that touches the DB, not just `expense_confirm`. This closes the gap
  noted in §4 and in `prd.md` §4.2 / §7.
- **Migrations — still deferred.** `Flask-Migrate` (Alembic) is not yet
  adopted. Deliberately left for a session where the user is present to
  run `flask db stamp head` against the real `instance/expenses.db`
  rather than have it happen unattended. See §2.2 for the exact order.
- **Production deployment tooling is ready, not yet used.** `wsgi.py` +
  `waitress` (Windows)/`gunicorn` (Linux) are wired up (README "How to
  Run"), but the app isn't actually running behind Nginx/systemd/TLS —
  that remains an infra decision, not a code gap.