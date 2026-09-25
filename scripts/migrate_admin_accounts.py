"""One-off schema migration for multi-admin accounts + per-expense activity
trail (see models/admin_user.py: AdminUser; models/audit.py:
AdminAuditLog.target_expense_id).

`db.create_all()` creates the brand-new `admin_users` table on its own,
but `admin_audit_log` already existed (from the earlier logistics-approval
change), so its new `target_expense_id` column needs to be added by hand.
Safe to run more than once; an already-present column is skipped.

Usage:
    venv\\Scripts\\python.exe scripts\\migrate_admin_accounts.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app import create_app
from extensions import db

NEW_COLUMNS = [
    ("target_expense_id", "INTEGER REFERENCES expenses(id)"),
]


def main():
    app = create_app()
    with app.app_context():
        existing = {
            row[1] for row in db.session.execute(text("PRAGMA table_info(admin_audit_log)")).fetchall()
        }
        for column, col_type in NEW_COLUMNS:
            if column in existing:
                print(f"Skipping '{column}' -- already present.")
                continue
            db.session.execute(text(f"ALTER TABLE admin_audit_log ADD COLUMN {column} {col_type}"))
            print(f"Added column '{column}' ({col_type}).")
        db.session.commit()
    print("Migration complete.")


if __name__ == "__main__":
    main()
