import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db


@pytest.fixture()
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    upload_root = tempfile.mkdtemp()
    invoice_dir = os.path.join(upload_root, "invoices")
    screenshot_dir = os.path.join(upload_root, "payment_screenshots")
    profile_dir = os.path.join(upload_root, "profile_images")
    for d in (invoice_dir, screenshot_dir, profile_dir):
        os.makedirs(d, exist_ok=True)

    flask_app = create_app(
        test_config={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "WTF_CSRF_ENABLED": False,
            "INVOICE_FOLDER": invoice_dir,
            "PAYMENT_SCREENSHOT_FOLDER": screenshot_dir,
            "PROFILE_IMAGE_FOLDER": profile_dir,
        }
    )

    yield flask_app

    with flask_app.app_context():
        db.engine.dispose()  # release the sqlite file handle (Windows locks it otherwise)
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db_session(app):
    with app.app_context():
        yield db.session
