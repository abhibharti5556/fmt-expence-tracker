# Task Tracker — Final Mile Techies Expense Management System

> **Revision note (2026-09-20):** Reprioritized after a full doc review.
> Items are now grouped by urgency instead of by category, and several
> new items were added (marked **[NEW]**). Nothing below is a commitment
> — it's a starting point for planning your next build phase. See
> `memory.md` for the full review log and rationale.
>
> **Implementation pass (2026-09-20, later):** Most of Priority 1 and the
> code-safe parts of Priority 2 are now implemented and tested (16
> passing pytest cases). See the "Done" section below and `memory.md` for
> exactly what changed, what was deliberately skipped, and why.

## Done (implemented in current codebase)

- [x] Role-based auth (Admin via env credentials, Employee via DB +
      hashed password), CSRF protection, session-based login/logout.
- [x] Admin: create/edit employee, reset password, activate/deactivate.
- [x] Admin: add money to employee (CREDIT transaction), recent-credits
      list.
- [x] Employee expense submission wizard (type → details+invoice →
      review → UPI pay → confirm+screenshot → success), both Logistics
      and Warehousing types.
- [x] Balance always derived (never stored/edited directly); enforced at
      submission time.
- [x] File upload validation (extension + size + content sniff) for
      profile photos, invoices, payment screenshots; authenticated-only
      file serving.
- [x] Admin: expenses audit list (filter/search/paginate) + detail view
      with invoice/screenshot.
- [x] Admin dashboard KPIs + 14-day/6-month trend charts + top-spender
      chart (Chart.js).
- [x] Admin analytics: per-employee drill-down + company-wide ranking.
- [x] Excel reports: Expense Report (Summary + Transactions sheets),
      Money Distribution Report — both filter-matched to the Reports
      screen.
- [x] Employee: own expense history (filter/paginate), profile edit,
      password change, profile photo remove.
- [x] Branded error pages (403/404/500).
- [x] `.env`-driven config, auto-created SQLite DB on first run.
- [x] **[2026-09-20]** SQLite writes serialized (`BEGIN IMMEDIATE` +
      `busy_timeout`) so the expense-confirm balance check can't race the
      insert. See `app.py: _configure_sqlite_locking`, `architecture.md` §7.
- [x] **[2026-09-20]** Login lockout (5 attempts / 10 min window / 15 min
      lockout, configurable) on both Admin and Employee login, keyed by
      identity+IP. `utils/rate_limit.py`, wired into `routes/auth.py`.
      In-memory — resets on restart, not shared across worker processes;
      fine at current single-process scale, revisit if/when multi-worker.
- [x] **[2026-09-20]** Session hardening: `PERMANENT_SESSION_LIFETIME`
      (default 8h, env-configurable), `HTTPONLY`, `SAMESITE=Lax`,
      `SECURE` (env-toggle for HTTPS). `session.permanent = True` set on
      login. See `config.py`.
- [x] **[2026-09-20]** Admin audit log — `AdminAuditLog` model
      (`models/audit.py`), logs employee create/edit/password-reset/
      status-toggle with admin username, timestamp, and a detail string.
      No dedicated UI yet (query the table directly) — matches the
      original scope in `rules.md` §8.
- [x] **[2026-09-20]** Docket Number duplicate check — blocks submission
      with a clear error naming the earlier transaction. App-level check
      (case-insensitive `ILIKE`), not a DB constraint — see note below.
- [x] **[2026-09-20]** Orphaned upload cleanup — invoice files are now
      deleted when a draft is abandoned (`expense_new`, logout) or
      overwritten (re-submitting a form). `scripts/cleanup_orphaned_uploads.py`
      is the backstop for session-expiry cases the in-app hooks can't catch.
- [x] **[2026-09-20]** Starter test suite — 16 pytest cases covering
      balance calculation, transaction ID generation/collision handling,
      and upload content validation. Runs against an isolated temp DB,
      never touches `instance/expenses.db`. `pytest -q` from repo root
      (needs `requirements-dev.txt`).
- [x] **[2026-09-20]** `requirements.txt` pinned to installed versions
      (+ `waitress` for Windows production serving); `requirements-dev.txt`
      added for `pytest`. `wsgi.py` added as the production entrypoint.
      README updated with production-run and test instructions.

## Priority 1 — Fix before real / production use

Remaining items — not done in the 2026-09-20 implementation pass because
each needs you present (running stateful commands against the real DB,
or making an infra/ops decision), not just a code change.

- [ ] No production WSGI server actually **deployed** — `wsgi.py` +
      `waitress`/`gunicorn` are ready (see README "How to Run"), but
      nothing is running behind Nginx/systemd/TLS yet. That's an infra
      step, not a code change.
- [ ] No backup strategy for `instance/expenses.db` or `uploads/` — needs
      a destination and schedule decision before it can be automated.
- [ ] **Docket Number uniqueness is app-level only, not a DB constraint.**
      A real unique index needs Flask-Migrate (see below) to apply
      safely to the existing `instance/expenses.db` without risking data
      loss — deferred together with migrations adoption.

## Priority 2 — Correctness / robustness

- [ ] **Flask-Migrate/Alembic adoption** — still not done. Deliberately
      deferred: adopting it means running `flask db init` +
      `flask db stamp head` against your real `instance/expenses.db`,
      which should happen with you present the first time, not silently.
      `architecture.md` §2.2 has the exact non-destructive step order.
      Once in place, promote the docket_no check above to a real DB
      constraint.
- [ ] **[NEW]** Raise password minimum from 6 to 8+ characters with a
      letter+digit requirement (employee creation, password reset,
      employee self-service password change). Flagged during the doc
      review (`rules.md` §2) but not yet implemented — small, no schema
      change, safe to do anytime.

## Priority 3 — Product gaps (likely future asks)

- [ ] Expense approval/rejection workflow — `payment_status` is
      architected to support it (`BALANCE_COUNTING_STATUSES` tuple) but
      nothing ever writes `VERIFIED`/`REJECTED` today; every expense is
      final the moment it's submitted. Given this app gates real money,
      consider raising this from "future ask" to "next build phase."
- [ ] No automatic UPI payment verification (webhook/API) — relies
      entirely on employee self-report (reference number + screenshot).
- [ ] No notifications (email/SMS/push) on money credit or expense
      submission.
- [ ] No multi-admin support — single shared Admin identity from `.env`.
      Worth reconsidering given operations span 5 locations (Delhi,
      Chakan, Raipur, Ahmedabad, Bangalore).
- [ ] No CSV/PDF export option — Excel only.

## Priority 4 — Ops / scale (plan for, don't need yet)

- [ ] SQLite's single-writer lock is fine at current scale but will
      become a real constraint once concurrent activity across multiple
      locations increases. Plan a Postgres migration path rather than
      being surprised by it later.

## Notes for future sessions

- `BALANCE_COUNTING_STATUSES` in `models/models.py` is the single lever
  for adding a payment-status workflow later — check there first before
  touching balance logic anywhere else.
- See `architecture.md` for the full request lifecycle and file layout,
  `rules.md` for exact validation constraints, `design.md` for the
  design-token/component system, and `prd.md` for scope/non-goals.