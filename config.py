import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-secret-key")

    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

    COMPANY_NAME = os.environ.get("COMPANY_NAME", "Final Mile Techies")
    COMPANY_UPI_ID = os.environ.get("COMPANY_UPI_ID", "company@upi")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
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
