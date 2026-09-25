"""Delete uploaded files that no longer belong to any DB row.

Most orphans are prevented at the source now (see routes/employee.py and
routes/auth.py, which delete a draft's invoice file when the wizard is
abandoned or the session ends). This script is the backstop for what
those hooks can't catch — an expired/cleared session cookie leaves a
draft's invoice on disk with nothing to trigger cleanup.

Only deletes files older than --min-age-hours (default 24) so an upload
that's mid-wizard right now is never touched.

Usage:
    venv\\Scripts\\python.exe scripts\\cleanup_orphaned_uploads.py --dry-run
    venv\\Scripts\\python.exe scripts\\cleanup_orphaned_uploads.py
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import Expense, User


def find_orphans(folder, referenced_filenames, min_age_seconds):
    if not os.path.isdir(folder):
        return []
    now = time.time()
    orphans = []
    for filename in os.listdir(folder):
        path = os.path.join(folder, filename)
        if not os.path.isfile(path):
            continue
        if filename in referenced_filenames:
            continue
        if now - os.path.getmtime(path) < min_age_seconds:
            continue
        orphans.append(path)
    return orphans


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="List orphans without deleting")
    parser.add_argument("--min-age-hours", type=float, default=24.0)
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        invoice_refs = {e.invoice_file for e in Expense.query.with_entities(Expense.invoice_file)}
        screenshot_refs = {
            e.payment_screenshot for e in Expense.query.with_entities(Expense.payment_screenshot)
        }
        profile_refs = {
            u.profile_image
            for u in User.query.with_entities(User.profile_image)
            if u.profile_image
        }

        targets = [
            (app.config["INVOICE_FOLDER"], invoice_refs),
            (app.config["PAYMENT_SCREENSHOT_FOLDER"], screenshot_refs),
            (app.config["PROFILE_IMAGE_FOLDER"], profile_refs),
        ]

        min_age_seconds = args.min_age_hours * 3600
        total = 0
        for folder, referenced in targets:
            orphans = find_orphans(folder, referenced, min_age_seconds)
            for path in orphans:
                total += 1
                if args.dry_run:
                    print(f"[dry-run] would delete: {path}")
                else:
                    os.remove(path)
                    print(f"deleted: {path}")

        print(f"\n{total} orphaned file(s) {'found' if args.dry_run else 'deleted'}.")


if __name__ == "__main__":
    main()
