"""One-off schema migration for the super-admin flag (see
models/admin_user.py: AdminUser.is_super_admin).

`db.create_all()` only creates tables that don't exist yet -- it never
alters an existing table -- so this column needs to be added by hand to
any database created before this change. Safe to run more than once;
an already-present column is skipped.

Usage:
    venv\\Scripts\\python.exe scripts\\migrate_super_admin.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app import create_app
from extensions import db


def main():
    app = create_app()
    with app.app_context():
        existing = {
            row[1] for row in db.session.execute(text("PRAGMA table_info(admin_users)")).fetchall()
        }
        if "is_super_admin" in existing:
            print("Skipping 'is_super_admin' -- already present.")
        else:
            db.session.execute(
                text("ALTER TABLE admin_users ADD COLUMN is_super_admin BOOLEAN NOT NULL DEFAULT 0")
            )
            print("Added column 'is_super_admin' (BOOLEAN NOT NULL DEFAULT 0).")
        db.session.commit()
    print("Migration complete.")


if __name__ == "__main__":
    main()
