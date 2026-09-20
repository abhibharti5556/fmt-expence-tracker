# Task Tracker — Final Mile Techies Expense Management System

> **Revision note (2026-09-20):** Reprioritized after a full doc review.
> Items are now grouped by urgency instead of by category, and several
> new items were added (marked **[NEW]**). Nothing below is a commitment
> — it's a starting point for planning your next build phase. See
> `memory.md` for the full review log and rationale.

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

## Priority 1 — Fix before real / production use

These directly protect money-movement correctness and account security.
None require a schema-breaking change, so they're cheap to do now and
expensive to skip.

- [ ] **[NEW]** Make the balance check in the expense-confirm step
      atomic with the `Expense` insert (single DB transaction). See
      `rules.md` §1 and `architecture.md` §7.
- [ ] **[NEW]** Add login rate-limiting/lockout on both Admin and
      Employee login routes. See `rules.md` §8.
- [ ] **[NEW]** Set an explicit session lifetime and harden session
      cookie flags (`HTTPONLY`, `SECURE`, `SAMESITE`). See `rules.md` §8.
- [ ] **[NEW]** Add an admin action audit log (employee edits, password
      resets, activate/deactivate) — not just money credits. See
      `rules.md` §8.
- [ ] **[NEW]** Add a uniqueness constraint on `docket_no` to catch
      duplicate logistics entries at submission time. See `rules.md` §3.
- [ ] No production WSGI server config documented (currently
      `app.run()` only). Move to gunicorn/waitress + Nginx + TLS +
      systemd before any real-world usage.
- [ ] **[NEW]** Adopt the standardized file structure in
      `architecture.md` §2.2 (`requirements.txt`, `.env.example`,
      `.gitignore`, `README.md`, `wsgi.py`, `migrations/`, `tests/`).
      Follow the migration order in §2.3 — it's additive, nothing in
      `routes/`, `utils/`, `templates/`, or `static/` changes.
- [ ] No backup strategy documented for `instance/expenses.db` or
      `uploads/`. Set up scheduled backups before trusting this with
      real company money.

## Priority 2 — Correctness / robustness

- [ ] Orphaned upload cleanup — if an employee uploads an invoice, then
      abandons the expense wizard before final confirm, the invoice file
      is never deleted (`routes/employee.py: expense_logistics/
      expense_warehousing` write to disk before the DB row exists).
- [ ] No DB migration tool (Alembic/Flask-Migrate) — schema changes today
      would require manually altering `instance/expenses.db` or deleting
      it (data loss). **Recommended to adopt now**, before the
      approval-workflow columns below are added, not after.
- [ ] No automated tests (unit or integration) exist anywhere in the
      repo — balance calculation, transaction ID generation, and file
      validation are all currently unverified except by manual testing.

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