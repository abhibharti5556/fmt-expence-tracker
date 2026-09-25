"""One-off schema migration for the logistics category + admin approval
feature (see models/models.py: Expense.category, Expense.rejection_reason,
Expense.reviewed_by, Expense.reviewed_at).

`db.create_all()` only creates tables that don't exist yet -- it never
alters an existing table -- so the columns added to the Expense model
need to be added by hand to any database created before this change.
Safe to run more than once; already-present columns are skipped.

Usage:
    venv\\Scripts\\python.exe scripts\\migrate_logistics_approval.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app import create_app
from extensions import db

NEW_COLUMNS = [
    ("category", "VARCHAR(50)"),
    ("rejection_reason", "VARCHAR(500)"),
    ("reviewed_by", "VARCHAR(120)"),
    ("reviewed_at", "DATETIME"),
]


def main():
    app = create_app()
    with app.app_context():
        existing = {
            row[1] for row in db.session.execute(text("PRAGMA table_info(expenses)")).fetchall()
        }
        for column, col_type in NEW_COLUMNS:
            if column in existing:
                print(f"Skipping '{column}' -- already present.")
                continue
            db.session.execute(text(f"ALTER TABLE expenses ADD COLUMN {column} {col_type}"))
            print(f"Added column '{column}' ({col_type}).")
        db.session.commit()
    print("Migration complete.")


if __name__ == "__main__":
    main()
