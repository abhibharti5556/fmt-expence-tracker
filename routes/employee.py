import re
from decimal import Decimal
from datetime import datetime

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    current_app, session, send_from_directory, abort,
)

from extensions import db
from models import (
    Expense, MoneyTransaction,
    EXPENSE_TYPE_LOGISTICS, EXPENSE_TYPE_WAREHOUSING, PAYMENT_STATUS_SUBMITTED,
)
from utils.decorators import employee_required, current_employee
from utils.helpers import (
    get_employee_balance, get_employee_totals, generate_transaction_id,
    validate_image, validate_document, save_uploaded_file, delete_uploaded_file,
)
from utils.upi import build_upi_link

employee_bp = Blueprint("employee", __name__, url_prefix="/employee")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MOBILE_RE = re.compile(r"^\+?\d{10,15}$")


def _discard_draft_invoice():
    """Delete the invoice file attached to the in-progress draft, if any.
    Called whenever a draft is abandoned or overwritten before it becomes
    a real Expense row, so uploads don't pile up on disk unreferenced."""
    draft = session.get("expense_draft")
    if draft and draft.get("invoice_file"):
        delete_uploaded_file(current_app.config["INVOICE_FOLDER"], draft["invoice_file"])


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@employee_bp.route("/dashboard")
@employee_required
def dashboard():
    user = current_employee()
    totals = get_employee_totals(user.id)
    recent_expenses = (
        Expense.query.filter_by(user_id=user.id).order_by(Expense.created_at.desc()).limit(5).all()
    )
    return render_template("employee/dashboard.html", totals=totals, recent_expenses=recent_expenses)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@employee_bp.route("/profile", methods=["GET", "POST"])
@employee_required
def profile():
    user = current_employee()

    if request.method == "POST":
        form = request.form
        errors = []

        name = form.get("name", "").strip()
        mobile = form.get("mobile", "").strip()
        email = form.get("email", "").strip()
        photo = request.files.get("photo")

        if not name:
            errors.append("Full name is required.")
        if not MOBILE_RE.match(mobile):
            errors.append("Enter a valid mobile number.")
        if not EMAIL_RE.match(email):
            errors.append("Enter a valid email address.")

        new_filename = None
        if photo and photo.filename:
            is_valid, error = validate_image(
                photo,
                current_app.config["ALLOWED_IMAGE_EXTENSIONS"],
                current_app.config["MAX_IMAGE_SIZE"],
            )
            if not is_valid:
                errors.append(error)
            else:
                new_filename = save_uploaded_file(
                    photo, current_app.config["PROFILE_IMAGE_FOLDER"], prefix=f"{user.employee_id}_"
                )

        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("employee/profile.html", user=user, form=form)

        user.name = name
        user.mobile = mobile
        user.email = email
        if new_filename:
            old_photo = user.profile_image
            user.profile_image = new_filename
            delete_uploaded_file(current_app.config["PROFILE_IMAGE_FOLDER"], old_photo)

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("employee.profile"))

    return render_template("employee/profile.html", user=user, form=None)


@employee_bp.route("/profile/photo/remove", methods=["POST"])
@employee_required
def remove_photo():
    user = current_employee()
    if user.profile_image:
        delete_uploaded_file(current_app.config["PROFILE_IMAGE_FOLDER"], user.profile_image)
        user.profile_image = None
        db.session.commit()
        flash("Profile photo removed.", "success")
    return redirect(url_for("employee.profile"))


@employee_bp.route("/profile/change-password", methods=["POST"])
@employee_required
def change_password():
    user = current_employee()
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not user.check_password(current_password):
        flash("Current password is incorrect.", "error")
    elif len(new_password) < 6:
        flash("New password must be at least 6 characters.", "error")
    elif new_password != confirm_password:
        flash("New passwords do not match.", "error")
    else:
        user.set_password(new_password)
        db.session.commit()
        flash("Password changed successfully.", "success")

    return redirect(url_for("employee.profile"))


# ---------------------------------------------------------------------------
# My Expenses
# ---------------------------------------------------------------------------

@employee_bp.route("/expenses")
@employee_required
def expenses():
    user = current_employee()
    query = Expense.query.filter_by(user_id=user.id)

    from_date = request.args.get("from_date", "").strip()
    to_date = request.args.get("to_date", "").strip()
    expense_type = request.args.get("expense_type", "").strip()
    status = request.args.get("status", "").strip()

    from sqlalchemy import func

    if from_date:
        query = query.filter(func.date(Expense.created_at) >= from_date)
    if to_date:
        query = query.filter(func.date(Expense.created_at) <= to_date)
    if expense_type:
        query = query.filter(Expense.expense_type == expense_type)
    if status:
        query = query.filter(Expense.payment_status == status)

    query = query.order_by(Expense.created_at.desc())
    page = request.args.get("page", 1, type=int)
    pagination = query.paginate(page=page, per_page=current_app.config["ITEMS_PER_PAGE"], error_out=False)

    return render_template(
        "employee/expenses.html", pagination=pagination, expenses=pagination.items, args=request.args
    )


@employee_bp.route("/expenses/<int:expense_id>")
@employee_required
def expense_detail(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if expense.user_id != current_employee().id:
        abort(403)
    return render_template("employee/expense_detail.html", expense=expense)


@employee_bp.route("/expenses/<int:expense_id>/invoice")
@employee_required
def expense_invoice(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if expense.user_id != current_employee().id:
        abort(403)
    as_attachment = request.args.get("download") == "1"
    return send_from_directory(
        current_app.config["INVOICE_FOLDER"], expense.invoice_file, as_attachment=as_attachment
    )


@employee_bp.route("/expenses/<int:expense_id>/payment-screenshot")
@employee_required
def expense_screenshot(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if expense.user_id != current_employee().id:
        abort(403)
    as_attachment = request.args.get("download") == "1"
    return send_from_directory(
        current_app.config["PAYMENT_SCREENSHOT_FOLDER"], expense.payment_screenshot, as_attachment=as_attachment
    )


# ---------------------------------------------------------------------------
# New Expense wizard: choose type -> details -> review -> pay -> confirm+submit -> success
# ---------------------------------------------------------------------------

@employee_bp.route("/expense/new")
@employee_required
def expense_new():
    _discard_draft_invoice()
    session.pop("expense_draft", None)
    return render_template("employee/expense_new.html", balance=get_employee_balance(current_employee().id))


@employee_bp.route("/expense/new/logistics", methods=["GET", "POST"])
@employee_required
def expense_logistics():
    user = current_employee()
    draft = session.get("expense_draft")
    existing = draft if draft and draft.get("expense_type") == EXPENSE_TYPE_LOGISTICS else {}

    if request.method == "POST":
        form = request.form
        errors = []

        amount_raw = form.get("amount", "").strip()
        docket_no = form.get("docket_no", "").strip()
        purpose = form.get("purpose", "").strip()
        approved_by = form.get("approved_by", "").strip()
        remarks = form.get("remarks", "").strip()
        invoice = request.files.get("invoice")

        try:
            amount = float(amount_raw)
            if amount <= 0:
                errors.append("Amount must be greater than ₹0.")
        except ValueError:
            errors.append("Enter a valid amount.")
            amount = 0

        if not docket_no:
            errors.append("Docket Number is required.")
        else:
            duplicate = Expense.query.filter(
                Expense.docket_no.isnot(None),
                Expense.docket_no.ilike(docket_no),
            ).first()
            if duplicate:
                errors.append(
                    f"Docket Number '{docket_no}' was already used in expense "
                    f"{duplicate.transaction_id}. Please check before submitting again."
                )
        if not purpose:
            errors.append("Purpose of Payment is required.")
        if not approved_by:
            errors.append("Approved By is required.")

        is_valid, file_error = validate_document(
            invoice, current_app.config["ALLOWED_DOCUMENT_EXTENSIONS"], current_app.config["MAX_DOCUMENT_SIZE"]
        )
        if not is_valid:
            errors.append(file_error)

        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("employee/expense_logistics_form.html", form=form, balance=get_employee_balance(user.id))

        invoice_filename = save_uploaded_file(
            invoice, current_app.config["INVOICE_FOLDER"], prefix=f"{user.employee_id}_"
        )

        _discard_draft_invoice()
        session["expense_draft"] = {
            "expense_type": EXPENSE_TYPE_LOGISTICS,
            "amount": str(amount),
            "docket_no": docket_no,
            "purpose": purpose,
            "approved_by": approved_by,
            "remarks": remarks,
            "invoice_file": invoice_filename,
        }
        session.modified = True
        return redirect(url_for("employee.expense_review"))

    return render_template(
        "employee/expense_logistics_form.html", form=existing, balance=get_employee_balance(user.id)
    )


@employee_bp.route("/expense/new/warehousing", methods=["GET", "POST"])
@employee_required
def expense_warehousing():
    user = current_employee()
    draft = session.get("expense_draft")
    existing = draft if draft and draft.get("expense_type") == EXPENSE_TYPE_WAREHOUSING else {}

    if request.method == "POST":
        form = request.form
        errors = []

        amount_raw = form.get("amount", "").strip()
        purpose = form.get("purpose", "").strip()
        reason = form.get("reason", "").strip()
        approved_by = form.get("approved_by", "").strip()
        remarks = form.get("remarks", "").strip()
        invoice = request.files.get("invoice")

        try:
            amount = float(amount_raw)
            if amount <= 0:
                errors.append("Amount must be greater than ₹0.")
        except ValueError:
            errors.append("Enter a valid amount.")
            amount = 0

        if not purpose:
            errors.append("Purpose of Expense is required.")
        if not reason:
            errors.append("Please explain why this expense is required.")
        if not approved_by:
            errors.append("Approved By is required.")

        is_valid, file_error = validate_document(
            invoice, current_app.config["ALLOWED_DOCUMENT_EXTENSIONS"], current_app.config["MAX_DOCUMENT_SIZE"]
        )
        if not is_valid:
            errors.append(file_error)

        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("employee/expense_warehousing_form.html", form=form, balance=get_employee_balance(user.id))

        invoice_filename = save_uploaded_file(
            invoice, current_app.config["INVOICE_FOLDER"], prefix=f"{user.employee_id}_"
        )

        _discard_draft_invoice()
        session["expense_draft"] = {
            "expense_type": EXPENSE_TYPE_WAREHOUSING,
            "amount": str(amount),
            "reason": reason,
            "purpose": purpose,
            "approved_by": approved_by,
            "remarks": remarks,
            "invoice_file": invoice_filename,
        }
        session.modified = True
        return redirect(url_for("employee.expense_review"))

    return render_template(
        "employee/expense_warehousing_form.html", form=existing, balance=get_employee_balance(user.id)
    )


@employee_bp.route("/expense/review")
@employee_required
def expense_review():
    draft = session.get("expense_draft")
    if not draft:
        flash("Please start a new expense.", "info")
        return redirect(url_for("employee.expense_new"))

    user = current_employee()
    balance = get_employee_balance(user.id)
    amount = Decimal(draft["amount"])
    insufficient = amount > balance

    return render_template(
        "employee/expense_review.html", draft=draft, amount=amount, balance=balance, insufficient=insufficient
    )


@employee_bp.route("/expense/pay")
@employee_required
def expense_pay():
    draft = session.get("expense_draft")
    if not draft:
        flash("Please start a new expense.", "info")
        return redirect(url_for("employee.expense_new"))

    user = current_employee()
    balance = get_employee_balance(user.id)
    amount = Decimal(draft["amount"])
    if amount > balance:
        flash("Insufficient balance. Please adjust the expense amount.", "error")
        return redirect(url_for("employee.expense_review"))

    upi_link = build_upi_link(
        current_app.config["COMPANY_UPI_ID"],
        current_app.config["COMPANY_NAME"],
        draft["amount"],
        f"FMT {draft['expense_type'].title()} Expense",
    )
    return render_template("employee/expense_pay.html", draft=draft, amount=amount, upi_link=upi_link)


@employee_bp.route("/expense/confirm", methods=["GET", "POST"])
@employee_required
def expense_confirm():
    draft = session.get("expense_draft")
    if not draft:
        flash("Please start a new expense.", "info")
        return redirect(url_for("employee.expense_new"))

    user = current_employee()
    amount = Decimal(draft["amount"])

    if request.method == "POST":
        errors = []
        balance = get_employee_balance(user.id)
        if amount > balance:
            flash(
                f"Insufficient Balance. Available Balance: {balance:,.2f} | Requested Amount: {amount:,.2f}",
                "error",
            )
            return redirect(url_for("employee.expense_review"))

        upi_reference_no = request.form.get("upi_reference_no", "").strip()
        screenshot = request.files.get("payment_screenshot")

        if len(upi_reference_no) < 4:
            errors.append("Please enter a valid UPI transaction/reference number.")

        is_valid, file_error = validate_image(
            screenshot, current_app.config["ALLOWED_IMAGE_EXTENSIONS"], current_app.config["MAX_IMAGE_SIZE"]
        )
        if not is_valid:
            errors.append(file_error)

        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("employee/expense_confirm.html", draft=draft, amount=amount)

        screenshot_filename = save_uploaded_file(
            screenshot, current_app.config["PAYMENT_SCREENSHOT_FOLDER"], prefix=f"{user.employee_id}_"
        )

        try:
            expense = Expense(
                transaction_id=generate_transaction_id(),
                user_id=user.id,
                expense_type=draft["expense_type"],
                amount=amount,
                docket_no=draft.get("docket_no"),
                purpose=draft["purpose"],
                reason=draft.get("reason"),
                approved_by=draft["approved_by"],
                remarks=draft.get("remarks") or None,
                upi_reference_no=upi_reference_no,
                payment_status=PAYMENT_STATUS_SUBMITTED,
                invoice_file=draft["invoice_file"],
                payment_screenshot=screenshot_filename,
            )
            db.session.add(expense)
            db.session.commit()
        except Exception:
            db.session.rollback()
            delete_uploaded_file(current_app.config["PAYMENT_SCREENSHOT_FOLDER"], screenshot_filename)
            flash("Something went wrong while submitting your expense. Please try again.", "error")
            return render_template("employee/expense_confirm.html", draft=draft, amount=amount)

        session.pop("expense_draft", None)
        flash("Expense submitted successfully.", "success")
        return redirect(url_for("employee.expense_success", expense_id=expense.id))

    return render_template("employee/expense_confirm.html", draft=draft, amount=amount)


@employee_bp.route("/expense/success/<int:expense_id>")
@employee_required
def expense_success(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if expense.user_id != current_employee().id:
        abort(403)
    return render_template("employee/expense_success.html", expense=expense)
