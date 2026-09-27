# Final Mile Techies — Expense Management System

An internal expense management web application for **Final Mile Techies**, a logistics and warehousing company. Tracks employee balances, logistics/warehousing expenses, UPI payment confirmation, invoices, and gives Admin a full financial dashboard with Excel exports.

Deeper project docs — product scope, architecture, business rules, design system, task tracker, and the decision log — live in [`docs/`](docs/).

## Features

- Admin and Employee login (separate, role-based)
- Admin-created, permanent Employee IDs (e.g. `EMP001`)
- Admin can add money to employees; balance is always computed (never manually edited)
- Two expense types — **Logistics** (with Docket Number) and **Warehousing** (with a required reason)
- Invoice/supporting document upload (PDF/JPG/PNG) with content validation
- UPI deep-link payment initiation + manual UPI reference entry + payment screenshot upload
- Automatic transaction IDs (`EXP-YYYYMMDD-NNNN`)
- Full admin audit view per expense: employee info, expense info, payment info, invoice, payment screenshot
- Employee-wise analytics with charts (Chart.js)
- Date-wise filters, search, and pagination
- Professional Excel reports (expense report + money distribution report) via pandas + openpyxl
- Secure file storage — all documents served through authenticated Flask routes, never as static files
- CSRF protection, hashed passwords, role-based access control
- Login lockout after repeated failed attempts, idle session expiry, hardened session cookies
- Admin action audit log (employee create/edit, password resets, activate/deactivate)
- Duplicate Docket Number detection at submission time
- SQLite writes are serialized (`BEGIN IMMEDIATE`) so a balance check can never race an expense insert

## Tech Stack

- **Backend:** Python, Flask, Flask-SQLAlchemy, SQLite, Flask-WTF (CSRF), Werkzeug (password hashing)
- **Frontend:** HTML5, CSS3, Bootstrap 5, vanilla JavaScript, Jinja2
- **Reports:** pandas, openpyxl
- **Charts:** Chart.js (CDN)
- **Icons:** Phosphor Icons (CDN)

## Installation

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Environment Variables

Copy `.env.example` to `.env` and fill in real values:

```text
SECRET_KEY=change-this-to-a-long-random-string
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-this-password
COMPANY_UPI_ID=company@upi
COMPANY_NAME=Final Mile Techies
FLASK_DEBUG=False
```

- `SECRET_KEY` — used for session signing and CSRF tokens. Use a long random string in production.
- `ADMIN_USERNAME` / `ADMIN_PASSWORD` — the single Admin account. Not stored in the database.
- `COMPANY_UPI_ID` — the UPI ID employees pay into when submitting an expense.
- `FLASK_DEBUG` — keep `False` in production; only enable for local development.
- `SESSION_LIFETIME_HOURS` — idle session expiry, default 8.
- `SESSION_COOKIE_SECURE` — set `True` once served over HTTPS; must stay `False` for local HTTP dev.
- `LOGIN_MAX_ATTEMPTS` / `LOGIN_ATTEMPT_WINDOW_MINUTES` / `LOGIN_LOCKOUT_MINUTES` — failed-login lockout tuning (defaults: 5 attempts / 10 minutes / 15-minute lockout).

**Never commit your real `.env` file** — it's already excluded via `.gitignore`.

## Database Setup

No manual migration step is needed. On first run, the app automatically creates `instance/expenses.db` (SQLite) with all required tables.

## How to Run

**Local development:**
```bash
python app.py
```

**Production** (behind a real WSGI server, not the Flask dev server):
```bash
# Windows
venv\Scripts\waitress-serve --listen=0.0.0.0:8000 wsgi:app

# Linux
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

The app runs at `http://127.0.0.1:5000` by default. On first run with an empty database, visiting the site takes you to a one-time setup screen to create the first Super Admin account — after that, log in there, create employee accounts, add money, and employees can then log in with their Employee ID.

## Maintenance

Uploaded invoice files are cleaned up automatically when an expense wizard is abandoned or the session ends. For files orphaned by an expired session (browser closed mid-wizard), run the sweep script periodically (e.g. a daily scheduled task):

```bash
python scripts/cleanup_orphaned_uploads.py --dry-run   # preview
python scripts/cleanup_orphaned_uploads.py              # delete
```

## File Uploads

Uploaded files are stored outside the `static/` folder and are only ever served through authenticated Flask routes (never as raw static files):

```text
uploads/profile_images/        Employee profile photos (JPG, JPEG, PNG, WEBP — max 5 MB)
uploads/invoices/               Invoice / supporting documents (PDF, JPG, JPEG, PNG — max 10 MB)
uploads/payment_screenshots/    UPI payment screenshots (JPG, JPEG, PNG — max 5 MB)
```

Every upload is validated by extension **and** file content (Pillow image verification / PDF signature check) before being saved under a generated, non-guessable filename.

## Excel Reports

From **Admin → Reports**, filter by date range, employee, expense type, or status, then:

- **Download Excel** — `Final_Mile_Techies_Expense_Report_<from>_to_<to>.xlsx`, with a Summary sheet (totals + employee-wise breakdown) and a Transactions sheet (full detail, frozen header row, autofilter, currency formatting).
- **Money Distribution Report** — `Final_Mile_Techies_Money_Distribution_Report.xlsx`, listing every money credit given to employees.

Both exports reflect exactly the filters currently applied on the Reports screen.

## Default Admin Configuration

Set via `.env` — see `ADMIN_USERNAME` / `ADMIN_PASSWORD` above. There is no admin account in the database; Admin authentication is checked directly against these environment variables on every login.
