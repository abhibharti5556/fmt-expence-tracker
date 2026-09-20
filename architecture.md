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
| **[NEW] Migrations** | Not yet present — **Alembic (via `Flask-Migrate`) is recommended before the schema grows further.** See §8. |
| **[NEW] Production server** | Not yet present — dev server (`app.run()`) only. **gunicorn/waitress behind Nginx is recommended before real usage at scale.** See §8. |

No frontend build step, no JS framework — schema is currently created via
`db.create_all()` on startup (see §8 for why this should change soon).

## 2. Application Structure

### 2.1 Current structure (as implemented)

```
app.py                 App factory (create_app), blueprint registration,
                        error handlers, jinja filter registration
config.py               Config class — env-driven settings
extensions.py            Shared, uninitialized extension instances (db, csrf)

models/
  models.py              SQLAlchemy models: User, MoneyTransaction, Expense
  __init__.py             Re-exports models + status/type constants

routes/
  auth.py                 /, /login, /login/admin, /login/employee, /logout,
                           profile-image serving
  admin.py                /admin/* — dashboard, employees, add-money,
                           expenses, analytics, reports (incl. Excel export)
  employee.py              /employee/* — dashboard, profile, expense
                           submission wizard, own expense history

utils/
  decorators.py            login_required / admin_required / employee_required,
                           current_employee() (reads g.current_user)
  helpers.py                Balance calculation, transaction ID generation,
                           file validation/storage, INR currency formatting
  upi.py                    UPI deep-link builder
  excel_reports.py          openpyxl report builders (Summary + Transactions,
                           Money Distribution)

templates/                Jinja2 templates, split by role (admin/, employee/,
                           auth/, errors/, partials/) with shared layout_admin.html
                           / layout_employee.html / base.html

static/                  CSS, JS, logo — never used for uploaded content

uploads/                 Runtime-created, outside static/:
  profile_images/, invoices/, payment_screenshots/

instance/                Runtime-created; holds expenses.db (SQLite)
```

This layout is sound for what it does today — blueprints, models, utils,
and templates are already cleanly separated. It's missing a few things a
standard Flask project has by this point, though: no migrations folder,
no tests, no pinned dependency list, no separation between the app
entrypoint and the production WSGI entrypoint, and no place for an audit
log. §2.2 below is the recommended target structure; §2.3 is how to get
there without breaking anything that already works.

### 2.2 **[NEW] Recommended structure**

```
final-mile-techies/
├── app.py                  App factory (create_app) — UNCHANGED, still
│                           the local-dev entrypoint (`python app.py`)
├── wsgi.py                 [NEW] Production entrypoint: `from app import
│                           create_app; app = create_app()`. This is what
│                           gunicorn/waitress point at — keeps `app.py`'s
│                           `if __name__ == "__main__": app.run(...)`
│                           block out of the production code path.
├── config.py               UNCHANGED
├── extensions.py            UNCHANGED
├── requirements.txt         [NEW] Pinned dependencies (`pip freeze`),
│                           so `venv` is reproducible from source control,
│                           not just a local artifact.
├── .env.example             [NEW] Every key `config.py` reads, with
│                           placeholder/dummy values — committed. The
│                           real `.env` stays local-only and gitignored.
├── .gitignore               [NEW] `.env`, `instance/`, `uploads/`,
│                           `venv/`, `__pycache__/`, `*.pyc`.
├── README.md                [NEW] Setup steps, how to run dev server,
│                           how to run migrations, how to run tests —
│                           currently this knowledge only exists in
│                           `memory.md`/`task.md`, which is fine for you
│                           but not for anyone else joining the project.
│
├── models/
│   ├── __init__.py           UNCHANGED — re-exports models + constants
│   ├── models.py              UNCHANGED — User, MoneyTransaction, Expense
│   └── audit.py               [NEW] AdminAuditLog model (rules.md §8) —
│                              kept in its own file since it's a
│                              cross-cutting concern, not part of the
│                              core money/expense ledger.
│
├── routes/
│   ├── __init__.py            [NEW if missing] so `routes/` is an
│                              explicit package
│   ├── auth.py                 UNCHANGED
│   ├── admin.py                 UNCHANGED
│   └── employee.py              UNCHANGED
│
├── utils/
│   ├── __init__.py             UNCHANGED/added if missing
│   ├── decorators.py            UNCHANGED
│   ├── helpers.py                UNCHANGED
│   ├── upi.py                     UNCHANGED
│   └── excel_reports.py            UNCHANGED
│
├── templates/                 UNCHANGED (see design.md §2 for the
│                              template/partials breakdown)
├── static/                    UNCHANGED
│
├── migrations/                 [NEW] Flask-Migrate/Alembic — created by
│                              `flask db init`, then `flask db migrate` /
│                              `flask db upgrade` replace `db.create_all()`
│                              as the way schema changes are applied.
│
├── tests/                      [NEW] pytest suite. Start with the three
│   ├── conftest.py             highest-value areas per `task.md`
│   ├── test_balance.py         Priority 2:
│   ├── test_auth.py            - balance calculation (get_employee_balance)
│   └── test_uploads.py         - transaction ID generation/collision retry
│                              - upload content validation (Pillow/PDF sniff)
│
├── logs/                       [NEW, optional] Only needed once you add
│                              file-based logging for the audit log /
│                              production error tracking — not required
│                              on day one.
│
├── uploads/                    UNCHANGED — runtime-created, outside
│                              static/: profile_images/, invoices/,
│                              payment_screenshots/
└── instance/                   UNCHANGED — runtime-created, holds
                                expenses.db (SQLite)
```

### 2.3 **[NEW] Migration path — how to adopt this without a rewrite**

This is additive, not a restructure of what already works. Do it in this
order so each step is independently safe to stop at:

1. **`requirements.txt`, `.env.example`, `.gitignore`, `README.md`** —
   zero code risk, do these first. `pip freeze > requirements.txt` from
   the existing `venv/`.
2. **`wsgi.py`** — one new two-line file; doesn't change `app.py` at all.
   Only matters once you actually deploy behind gunicorn/waitress.
3. **`migrations/`** — `pip install Flask-Migrate`, wire `Migrate(app,
   db)` into `extensions.py`, run `flask db init`, then `flask db
   stamp head` against the *existing* database (tells Alembic "this
   schema already matches this migration state" without trying to
   recreate it). From this point on, schema changes go through `flask db
   migrate` + `flask db upgrade` instead of relying on `db.create_all()`.
4. **`tests/`** — add incrementally; don't block anything else on
   reaching full coverage. Balance calculation and transaction ID
   generation are the highest-value first tests since they're the two
   places a silent bug would directly affect money.
5. **`models/audit.py`** — only once you're ready to implement the
   admin audit log from `rules.md` §8; it's a new table, so it goes
   through the migration flow from step 3.

None of this touches `routes/`, `utils/`, `templates/`, or `static/` —
those stay exactly as they are.

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

**[NEW]** `docket_no` currently has **no uniqueness constraint**. Nothing
stops the same docket number being submitted twice (by the same or a
different employee), which weakens the audit trail the PRD promises.
Recommended fix: add a unique index on `docket_no` (scoped to non-null
values), or at minimum a warning-on-duplicate check in
`routes/employee.py` before the review step.

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

**[UPDATED — see §7]** The balance check during expense submission is
currently a *read-then-write* (query the balance, then later write the
expense row) rather than a single atomic operation. This is safe today
only because the dev server is single-process/single-threaded. It stops
being safe the moment this app runs under a real WSGI server with
multiple workers/threads (see §7 for the fix).

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
  **[NEW]** No session expiry (`PERMANENT_SESSION_LIFETIME`) is currently
  set — a session cookie is valid indefinitely once issued. Recommend
  setting an explicit lifetime (e.g. 8–12 hours) plus
  `SESSION_COOKIE_SECURE=True` / `SESSION_COOKIE_HTTPONLY=True` once
  served over HTTPS.
- **[NEW]** No login rate-limiting or lockout exists on either the Admin
  or Employee login route — brute-force attempts are only slowed by
  `secrets.compare_digest`'s constant-time comparison, not blocked. See
  `rules.md` §8 for the recommended rule.
- **[NEW]** No audit trail exists for Admin actions beyond `created_by`
  on money credits — edits to employee records, password resets, and
  activation/deactivation are not logged with who/when. See `rules.md` §8.

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
  expense row (only an orphaned invoice upload, which is not currently
  garbage-collected — see `task.md`).
- **Transaction ID generation retries on collision** rather than trusting
  a naive `count + 1`, to handle same-second concurrent submissions.
- **[NEW] Balance-check atomicity fix (recommended).** Wrap the final
  balance re-check and the `Expense` insert in `routes/employee.py:
  expense_confirm` inside a single `db.session.begin()` block, and
  re-read the balance *inside* that transaction immediately before the
  insert (rather than trusting the value computed earlier in the wizard).
  On SQLite this also means opening the connection in
  `IMMEDIATE`/`EXCLUSIVE` mode for that write to avoid a write-write race
  once the app runs under more than one worker process. This closes the
  gap noted in §4 and in `prd.md` §4.2 / §7.
- **[NEW] Migrations.** Introduce `Flask-Migrate` (Alembic) now, before
  adding the approval-workflow columns/tables that `task.md` flags as
  likely. Converting from `db.create_all()` later, after production data
  already exists, is much more painful than adopting migrations early.
- **[NEW] Production deployment.** The dev server (`app.run()`) is not
  meant for real traffic — no worker concurrency model, no crash
  recovery, debug mode risks leaking stack traces if ever left on.
  Recommended path: `gunicorn` (or `waitress` on Windows) behind Nginx,
  with `FLASK_DEBUG=False` enforced outside local dev, TLS termination at
  Nginx, and the app run as a systemd service for auto-restart.