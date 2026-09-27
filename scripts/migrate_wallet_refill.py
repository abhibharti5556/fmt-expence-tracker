"""One-off schema migration for the wallet-refill-request feature (see
models/models.py: User.last_refill_request_at).

`db.create_all()` only creates tables that don't exist yet -- it never
alters an existing table -- so this column needs to be added by hand to
any database created before this change. Safe to run more than once;
an already-present column is skipped.

Usage:
    venv\\Scripts\\python.exe scripts\\migrate_wallet_refill.py
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
            row[1] for row in db.session.execute(text("PRAGMA table_info(users)")).fetchall()
        }
        if "last_refill_request_at" in existing:
            print("Skipping 'last_refill_request_at' -- already present.")
        else:
            db.session.execute(text("ALTER TABLE users ADD COLUMN last_refill_request_at DATETIME"))
            print("Added column 'last_refill_request_at' (DATETIME).")
        db.session.commit()
    print("Migration complete.")


if __name__ == "__main__":
    main()
