import io
import os
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from PIL import Image
from werkzeug.utils import secure_filename

from extensions import db
from models import (
    MoneyTransaction,
    Expense,
    TRANSACTION_TYPE_CREDIT,
    BALANCE_COUNTING_STATUSES,
    EXPENSE_TYPE_LOGISTICS,
    EXPENSE_TYPE_WAREHOUSING,
)


# ---------------------------------------------------------------------------
# Transaction IDs
# ---------------------------------------------------------------------------

def generate_transaction_id():
    """EXP-YYYYMMDD-NNNN, sequence resets daily. Retries on the rare collision
    instead of trusting a naive count (two submissions the same second)."""
    today_str = date.today().strftime("%Y%m%d")
    prefix = f"EXP-{today_str}-"
    count_today = Expense.query.filter(Expense.transaction_id.like(f"{prefix}%")).count()
    seq = count_today + 1
    while True:
        candidate = f"{prefix}{seq:04d}"
        if not Expense.query.filter_by(transaction_id=candidate).first():
            return candidate
        seq += 1


# ---------------------------------------------------------------------------
# Balance calculation - single source of truth used everywhere
# ---------------------------------------------------------------------------

def get_total_credited(user_id):
    total = (
        db.session.query(db.func.coalesce(db.func.sum(MoneyTransaction.amount), 0))
        .filter(
            MoneyTransaction.user_id == user_id,
            MoneyTransaction.transaction_type == TRANSACTION_TYPE_CREDIT,
        )
        .scalar()
    )
    return Decimal(total or 0)


def get_total_spent(user_id, expense_type=None):
    query = db.session.query(db.func.coalesce(db.func.sum(Expense.amount), 0)).filter(
        Expense.user_id == user_id,
        Expense.payment_status.in_(BALANCE_COUNTING_STATUSES),
    )
    if expense_type:
        query = query.filter(Expense.expense_type == expense_type)
    return Decimal(query.scalar() or 0)


def get_employee_balance(user_id):
    return get_total_credited(user_id) - get_total_spent(user_id)


def get_employee_totals(user_id):
    received = get_total_credited(user_id)
    logistics = get_total_spent(user_id, EXPENSE_TYPE_LOGISTICS)
    warehousing = get_total_spent(user_id, EXPENSE_TYPE_WAREHOUSING)
    spent = logistics + warehousing
    return {
        "received": received,
        "spent": spent,
        "logistics": logistics,
        "warehousing": warehousing,
        "balance": received - spent,
    }


# ---------------------------------------------------------------------------
# File validation & storage
# ---------------------------------------------------------------------------

def _get_extension(filename):
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def _check_basic(file_storage, allowed_extensions, max_size_bytes):
    if file_storage is None or file_storage.filename == "":
        return False, "Please choose a file to upload."

    ext = _get_extension(file_storage.filename)
    if ext not in allowed_extensions:
        return False, f"Unsupported file type. Allowed: {', '.join(sorted(allowed_extensions)).upper()}."

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size == 0:
        return False, "The selected file is empty."
    if size > max_size_bytes:
        return False, f"File is too large. Maximum size is {max_size_bytes // (1024 * 1024)} MB."

    return True, ext


def validate_image(file_storage, allowed_extensions, max_size_bytes):
    """Extension allow-list + real image content check (Pillow) + size cap."""
    ok, ext_or_error = _check_basic(file_storage, allowed_extensions, max_size_bytes)
    if not ok:
        return False, ext_or_error

    try:
        buffer = io.BytesIO(file_storage.stream.read())
        file_storage.stream.seek(0)
        image = Image.open(buffer)
        image.verify()
    except Exception:
        return False, "The uploaded file is not a valid image."

    return True, None


def validate_document(file_storage, allowed_extensions, max_size_bytes):
    """Extension allow-list + content sniff (PDF magic bytes or real image) + size cap."""
    ok, ext_or_error = _check_basic(file_storage, allowed_extensions, max_size_bytes)
    if not ok:
        return False, ext_or_error
    ext = ext_or_error

    if ext == "pdf":
        header = file_storage.stream.read(8)
        file_storage.stream.seek(0)
        if not header.startswith(b"%PDF-"):
            return False, "The uploaded file is not a valid PDF."
    else:
        try:
            buffer = io.BytesIO(file_storage.stream.read())
            file_storage.stream.seek(0)
            image = Image.open(buffer)
            image.verify()
        except Exception:
            return False, "The uploaded file is not a valid image."

    return True, None


def save_uploaded_file(file_storage, folder, prefix=""):
    """Save with a generated secure filename. Never trusts the original name."""
    ext = _get_extension(secure_filename(file_storage.filename))
    unique_name = f"{prefix}{uuid.uuid4().hex}.{ext}"
    file_storage.stream.seek(0)
    file_storage.save(os.path.join(folder, unique_name))
    return unique_name


def delete_uploaded_file(folder, filename):
    if not filename:
        return
    path = os.path.join(folder, filename)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Display formatting
# ---------------------------------------------------------------------------

def format_inr(value):
    """Indian digit grouping, e.g. Decimal('1234567') -> '₹12,34,567.00'."""
    try:
        value = Decimal(value)
    except (InvalidOperation, TypeError):
        value = Decimal(0)

    negative = value < 0
    value = abs(value)
    whole = int(value)
    fraction = int((value - whole) * 100)

    s = str(whole)
    if len(s) <= 3:
        grouped = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        grouped = ",".join(parts) + "," + last3

    result = f"₹{grouped}.{fraction:02d}"
    return f"-{result}" if negative else result
