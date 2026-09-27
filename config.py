import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _str_env(name, default):
    """os.environ.get(name, default) only falls back to `default` when the
    key is absent, not when a dashboard (Vercel, Render, etc.) has it
    present but left blank -- which silently produces "" instead of the
    intended default. That's a crash later for SECRET_KEY specifically
    (Flask refuses to touch the session with an empty secret key) and
    silently wrong behavior for the rest. Treat blank the same as unset
    for every setting that has a real default; leave truly optional
    settings (SMTP_HOST, SMTP_USERNAME, ...) on plain os.environ.get,
    since "" is already their correct/intended unset value."""
    value = os.environ.get(name, "").strip()
    return value if value else default


def _int_env(name, default):
    value = os.environ.get(name, "").strip()
    return int(value) if value else default


# Vercel's deployed filesystem is read-only except /tmp, and /tmp is wiped
# between invocations (so this is not real persistence -- data written
# here can vanish at any time). This only exists so the app can boot and
# demo on Vercel at all; it is not a substitute for a real deployment
# target with a persistent disk.
IS_VERCEL = os.environ.get("VERCEL") == "1"
_UPLOAD_BASE = "/tmp/uploads" if IS_VERCEL else os.path.join(BASE_DIR, "uploads")


class Config:
    SECRET_KEY = _str_env("SECRET_KEY", "dev-insecure-secret-key")

    ADMIN_USERNAME = _str_env("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = _str_env("ADMIN_PASSWORD", "admin")

    COMPANY_NAME = _str_env("COMPANY_NAME", "Final Mile Techies")
    COMPANY_UPI_ID = _str_env("COMPANY_UPI_ID", "company@upi")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = _UPLOAD_BASE
    PROFILE_IMAGE_FOLDER = os.path.join(UPLOAD_FOLDER, "profile_images")
    INVOICE_FOLDER = os.path.join(UPLOAD_FOLDER, "invoices")
    PAYMENT_SCREENSHOT_FOLDER = os.path.join(UPLOAD_FOLDER, "payment_screenshots")

    MAX_CONTENT_LENGTH = 12 * 1024 * 1024  # 12 MB hard cap per request

    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
    ALLOWED_DOCUMENT_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}

    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
    MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10 MB

    ITEMS_PER_PAGE = 20

    FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "False") == "True"

    # Idle sessions expire after this many hours; refreshed on each request
    # (Flask's default SESSION_REFRESH_EACH_REQUEST) so an active user is
    # never logged out mid-work, only after real inactivity.
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=_int_env("SESSION_LIFETIME_HOURS", 8)
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Set SESSION_COOKIE_SECURE=True in .env once the app is served over
    # HTTPS. Left False by default so local HTTP dev keeps working.
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "False") == "True"

    # Failed-login lockout (see utils/rate_limit.py)
    LOGIN_MAX_ATTEMPTS = _int_env("LOGIN_MAX_ATTEMPTS", 5)
    LOGIN_ATTEMPT_WINDOW_MINUTES = _int_env("LOGIN_ATTEMPT_WINDOW_MINUTES", 10)
    LOGIN_LOCKOUT_MINUTES = _int_env("LOGIN_LOCKOUT_MINUTES", 15)

    # Outbound mail for expense-approval notifications (see utils/mailer.py).
    # Leave SMTP_HOST blank to skip sending entirely -- nothing else in the
    # approval workflow depends on mail actually going out.
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = _int_env("SMTP_PORT", 587)
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "True") == "True"
    MAIL_FROM_ADDRESS = os.environ.get("MAIL_FROM_ADDRESS", "")
    MAIL_FROM_NAME = _str_env("MAIL_FROM_NAME", "Final Mile Techies Expense Tracker")
