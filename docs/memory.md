# Project Memory — Final Mile Techies Expense Management System

Running log of decisions, context, and non-obvious reasoning for this
project — the "why" that isn't visible from reading the code alone.
Append new entries at the top (most recent first). Keep entries short;
link to `prd.md` / `architecture.md` / `rules.md` / `design.md` / `task.md`
for anything that belongs there instead.

---

## 2026-09-20 (latest) — Implementation pass on the Priority 1 doc-review findings

Implemented most of `task.md`'s Priority 1 list, plus the code-safe parts
of Priority 2, against the real codebase (not just docs this time).
git was initialized first (baseline commit `ccebc59`) specifically because
this pass touches auth/session behavior and adds new files — the user
confirmed they wanted a rollback point before starting.

**What changed, by file:**
- `app.py` — `_configure_sqlite_locking()`: SQLite engine now issues
  `BEGIN IMMEDIATE` on every transaction + `PRAGMA busy_timeout=5000`.
  This closes the balance-check race identified in the doc review
  without any app-level locking code, because SQLite's single-writer
  lock does the serialization once it's taken at transaction start
  instead of at first write. Also added `create_app(test_config=None)`
  so the test suite can point at an isolated DB.
- `config.py` — `PERMANENT_SESSION_LIFETIME`, `SESSION_COOKIE_HTTPONLY`,
  `SESSION_COOKIE_SAMESITE`, `SESSION_COOKIE_SECURE` (env-toggle),
  `LOGIN_MAX_ATTEMPTS`/`LOGIN_ATTEMPT_WINDOW_MINUTES`/`LOGIN_LOCKOUT_MINUTES`.
- `utils/rate_limit.py` (new) — in-memory failed-login tracker, wired
  into both login routes in `routes/auth.py`. Deliberately simple (dict +
  lock, not Redis/DB) since the app is single-process; flagged in
  `task.md` as something to revisit only if the app becomes multi-worker.
- `models/audit.py` (new) — `AdminAuditLog` + `log_admin_action()`.
  Wired into `routes/admin.py` for employee create/edit/password-reset/
  status-toggle. New table, created automatically by the existing
  `db.create_all()` — confirmed via `sqlite3` that `admin_audit_log` now
  exists in `instance/expenses.db` alongside the original three tables,
  with no changes to those three.
- `routes/employee.py` — Docket Number duplicate check (app-level query,
  case-insensitive) in the Logistics form handler. Also added
  `_discard_draft_invoice()`, called from `expense_new()` and both form
  handlers, so abandoning or overwriting a draft deletes its orphaned
  invoice file. `routes/auth.py: logout()` does the same.
- `scripts/cleanup_orphaned_uploads.py` (new) — sweeps files not
  referenced by any DB row and older than 24h (configurable); backstop
  for the case the in-app hooks can't catch (session expired, browser
  closed mid-wizard).
- `wsgi.py` (new), `requirements.txt` (pinned to installed versions +
  `waitress`), `requirements-dev.txt` (new, `pytest`), `.env.example`
  (new optional vars documented), `README.md` (production run, test run,
  maintenance script instructions).
- `tests/` (new) — `conftest.py` + 16 pytest cases across
  `test_balance.py`, `test_transaction_id.py`, `test_uploads.py`. All
  pass. Verified via the actual dev server too: restarted `app.py`,
  hammered `/login/admin` with 5 wrong-password POSTs (real CSRF tokens,
  cookie jar) and confirmed the 5th response returns the lockout message
  and a 6th is still blocked.

**Deliberately NOT done, and why:**
- **Flask-Migrate/Alembic adoption** — needs `flask db stamp head` run
  against the real `instance/expenses.db` with the user present the
  first time, not silently by an agent. `architecture.md` §2.3 has the
  order to follow when ready.
- **A real DB unique constraint on `docket_no`** — same reason; the
  app-level check added now is a reasonable interim (catches the same
  mistake, just not race-proof under concurrent submission of the exact
  same docket number in the same instant, which is an unlikely scenario
  for this app's usage pattern).
- **Actual production deployment** (Nginx/systemd/TLS) — infra outside
  this codebase; `wsgi.py` + `waitress`/`gunicorn` are ready, nothing is
  running behind them yet.
- **Backup automation** — needs a destination/schedule decision first.
- **Priority 3 product features** (approval workflow, notifications,
  multi-admin, CSV export) — untouched, per the standing open questions
  below; these need a product decision, not just an implementation.

## 2026-09-20 (later same day) — Full doc review and upgrade pass

Reviewed all six docs end-to-end for consistency and gaps, and upgraded
`prd.md`, `architecture.md`, `rules.md`, and `task.md` accordingly
(`design.md` was reviewed and found accurate as-is — no changes needed).

**What was found, not previously documented anywhere:**
- The balance check during expense submission is read-then-write, not
  atomic with the expense insert — safe only under the current
  single-process dev server, not safe once running under a real
  multi-worker production server. → `rules.md` §1, `architecture.md` §7.
- No session expiry configured — sessions are valid indefinitely.
  → `rules.md` §2/§8.
- No login rate-limiting/lockout on either login route.
  → `rules.md` §8.
- No admin action audit log beyond `created_by` on money credits — edits
  to employee records aren't traceable to an admin/time. → `rules.md` §8.
- `docket_no` has no uniqueness constraint, so duplicate docket numbers
  can be logged without any warning. → `rules.md` §3.
- Password minimum (6 chars, no complexity rule) is thin for a
  money-gating app. → `rules.md` §2.

**Reprioritization decision:** moved "no production WSGI server," "no
backups," "no migrations tool," and the new items above into a
Priority-1/2 tier in `task.md`, ahead of product features like the
approval workflow — reasoning: this app moves real company money across
5 locations, so integrity/security fixes outrank new features until
they're closed. The approval workflow itself was also bumped from a pure
"future ask" to "worth considering for the next build phase," since it's
the most direct mitigation for the "every expense is final on submit"
risk.

**Nothing in the original implementation was found to be broken** — all
of the above are gaps to close before scaling up, not bugs in what's
already built.

## 2026-09-20 (later still) — Standardized file/folder structure added

Added a recommended target project structure to `architecture.md` §2.2
(alongside the existing structure, kept as §2.1 for reference): adds
`requirements.txt`, `.env.example`, `.gitignore`, `README.md`, `wsgi.py`,
`migrations/`, and `tests/`. `models/audit.py` is the planned home for
the admin audit log from `rules.md` §8. A step-by-step, non-breaking
adoption order is in `architecture.md` §2.3 — none of it touches
`routes/`, `utils/`, `templates/`, or `static/`, which were already
well-organized. Tracked as a task in `task.md`.

## 2026-09-20 — Docs bootstrapped from existing codebase

`prd.md`, `architecture.md`, `rules.md`, `design.md`, `task.md`, and this
file were written by reading the actual implementation (models, routes,
utils, config, templates, CSS tokens) rather than from a spec — this was
already a working app before the docs existed. Treat the docs as a
snapshot of what's true as of this date; re-verify against the code
before trusting a specific claim in a future session, same as with any
memory.

Confirmed working: app runs via `python app.py` (or the project's `venv`)
at `http://127.0.0.1:5000`, dependencies already installed in `venv/`,
DB auto-creates in `instance/expenses.db` on first run.

## Key decisions worth remembering

- **Balance is always derived, never stored.** Every "credit balance
  directly" instinct should be resisted — go through
  `utils/helpers.py: get_employee_balance` instead. This was clearly a
  deliberate choice (see `architecture.md` §4) to guarantee the balance
  can never drift from the transaction/expense ledger.
- **`payment_status` is a plain string, not an enum, on purpose** — the
  code comment in `models/models.py` explicitly says this is to allow
  future statuses (`VERIFIED`/`REJECTED`) without a migration. Only
  `SUBMITTED` is ever written today. If an approval workflow is ever
  requested, `BALANCE_COUNTING_STATUSES` is the one place that decides
  what still counts toward balance/KPIs/reports.
- **No Admin database row** — Admin is authenticated straight against
  `.env` (`ADMIN_USERNAME`/`ADMIN_PASSWORD`). Multi-admin support would
  require introducing an actual Admin table/role, not just relaxing a
  check.
- **Expense submission is a session-backed wizard**, not a single form
  or a DB draft row — `session["expense_draft"]`. Nothing hits the
  `expenses` table until the final confirm step. Known gap: an abandoned
  wizard leaves the already-uploaded invoice file on disk with nothing
  referencing it (tracked in `task.md`).
- **File uploads are validated by content, not just extension** — Pillow
  `Image.verify()` for images, PDF magic-byte sniff for PDFs — a
  deliberate defense against a renamed malicious file passing extension
  checks alone.

## Open questions for the user (not yet answered)

- Is an expense approval/rejection workflow actually planned, or is
  "submit = final" intentional and permanent for this org's process?
- Any plan to move off SQLite / add Alembic migrations, or is the
  current scale expected to stay small enough that `db.create_all()` is
  fine indefinitely?
- Deployment target — still just the Flask dev server for internal use,
  or is a production WSGI setup (gunicorn/waitress + reverse proxy)
  expected at some point?