import re
from datetime import datetime, date, timedelta

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    current_app, send_from_directory, send_file, abort,
)
from sqlalchemy import func, or_

from extensions import db
from models import (
    User, MoneyTransaction, Expense,
    STATUS_ACTIVE, STATUS_INACTIVE, TRANSACTION_TYPE_CREDIT,
    EXPENSE_TYPE_LOGISTICS, EXPENSE_TYPE_WAREHOUSING, BALANCE_COUNTING_STATUSES,
    log_admin_action,
)
from utils.decorators import admin_required
from utils.helpers import get_employee_balance, get_employee_totals, get_total_spent, get_total_credited
from utils.excel_reports import build_expense_report, build_money_distribution_report

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MOBILE_RE = re.compile(r"^\+?\d{10,15}$")
EMPLOYEE_ID_RE = re.compile(r"^[A-Za-z0-9\-]{3,20}$")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    total_distributed = get_total_credited_all()
    total_expenses = get_total_spent_all()
    logistics_total = get_total_spent_all(EXPENSE_TYPE_LOGISTICS)
    warehousing_total = get_total_spent_all(EXPENSE_TYPE_WAREHOUSING)
    available_balance = total_distributed - total_expenses
    active_employees = User.query.filter_by(status=STATUS_ACTIVE).count()
    total_transactions = Expense.query.count()

    today = date.today()
    today_expenses = (
        db.session.query(func.coalesce(func.sum(Expense.amount), 0))
        .filter(
            Expense.payment_status.in_(BALANCE_COUNTING_STATUSES),
            func.date(Expense.created_at) == today.isoformat(),
        )
        .scalar()
    )

    daily_labels, daily_values = _daily_expense_trend(days=14)
    monthly_labels, monthly_values = _monthly_expense_trend(months=6)
    employee_labels, employee_values = _employee_wise_spending(limit=10)

    kpis = {
        "total_distributed": total_distributed,
        "total_expenses": total_expenses,
        "logistics_total": logistics_total,
        "warehousing_total": warehousing_total,
        "available_balance": available_balance,
        "active_employees": active_employees,
        "total_transactions": total_transactions,
        "today_expenses": today_expenses or 0,
    }

    return render_template(
        "admin/dashboard.html",
        kpis=kpis,
        daily_labels=daily_labels,
        daily_values=daily_values,
        monthly_labels=monthly_labels,
        monthly_values=monthly_values,
        employee_labels=employee_labels,
        employee_values=employee_values,
    )


def get_total_credited_all():
    total = db.session.query(func.coalesce(func.sum(MoneyTransaction.amount), 0)).filter(
        MoneyTransaction.transaction_type == TRANSACTION_TYPE_CREDIT
    ).scalar()
    return total or 0


def get_total_spent_all(expense_type=None):
    query = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.payment_status.in_(BALANCE_COUNTING_STATUSES)
    )
    if expense_type:
        query = query.filter(Expense.expense_type == expense_type)
    return query.scalar() or 0


def _daily_expense_trend(days=14):
    today = date.today()
    start = today - timedelta(days=days - 1)
    rows = (
        db.session.query(
            func.date(Expense.created_at).label("day"),
            func.sum(Expense.amount),
        )
        .filter(
            Expense.payment_status.in_(BALANCE_COUNTING_STATUSES),
            func.date(Expense.created_at) >= start.isoformat(),
        )
        .group_by("day")
        .all()
    )
    totals_by_day = {r[0]: float(r[1]) for r in rows}
    labels, values = [], []
    for i in range(days):
        d = start + timedelta(days=i)
        labels.append(d.strftime("%d %b"))
        values.append(totals_by_day.get(d.isoformat(), 0))
    return labels, values


def _monthly_expense_trend(months=6):
    rows = (
        db.session.query(
            func.strftime("%Y-%m", Expense.created_at).label("month"),
            func.sum(Expense.amount),
        )
        .filter(Expense.payment_status.in_(BALANCE_COUNTING_STATUSES))
        .group_by("month")
        .all()
    )
    totals_by_month = {r[0]: float(r[1]) for r in rows}

    labels, values = [], []
    today = date.today()
    year, month = today.year, today.month
    month_keys = []
    for _ in range(months):
        month_keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    month_keys.reverse()
    for key in month_keys:
        y, m = key.split("-")
        label = datetime(int(y), int(m), 1).strftime("%b %Y")
        labels.append(label)
        values.append(totals_by_month.get(key, 0))
    return labels, values


def _employee_wise_spending(limit=10):
    rows = (
        db.session.query(User.name, func.sum(Expense.amount).label("total"))
        .join(Expense, Expense.user_id == User.id)
        .filter(Expense.payment_status.in_(BALANCE_COUNTING_STATUSES))
        .group_by(User.id)
        .order_by(func.sum(Expense.amount).desc())
        .limit(limit)
        .all()
    )
    return [r[0] for r in rows], [float(r[1]) for r in rows]


# ---------------------------------------------------------------------------
# Employees
# ---------------------------------------------------------------------------

@admin_bp.route("/employees")
@admin_required
def employees():
    q = request.args.get("q", "").strip()
    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.name.ilike(like), User.employee_id.ilike(like)))
    users = query.order_by(User.created_at.desc()).all()

    rows = []
    for u in users:
        totals = get_employee_totals(u.id)
        rows.append({"user": u, **totals})

    return render_template("admin/employees.html", rows=rows, q=q)


@admin_bp.route("/employees/add", methods=["GET", "POST"])
@admin_required
def add_employee():
    if request.method == "POST":
        form = request.form
        errors = []

        name = form.get("name", "").strip()
        employee_id = form.get("employee_id", "").strip().upper()
        mobile = form.get("mobile", "").strip()
        email = form.get("email", "").strip()
        password = form.get("password", "")
        status = form.get("status", STATUS_ACTIVE)
        initial_balance_raw = form.get("initial_balance", "0").strip() or "0"

        if not name:
            errors.append("Employee name is required.")
        if not EMPLOYEE_ID_RE.match(employee_id):
            errors.append("Employee ID must be 3-20 characters (letters, numbers, hyphens).")
        elif User.query.filter_by(employee_id=employee_id).first():
            errors.append(f"Employee ID '{employee_id}' is already in use.")
        if not MOBILE_RE.match(mobile):
            errors.append("Enter a valid mobile number.")
        if not EMAIL_RE.match(email):
            errors.append("Enter a valid email address.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if status not in (STATUS_ACTIVE, STATUS_INACTIVE):
            status = STATUS_ACTIVE

        try:
            initial_balance = float(initial_balance_raw)
            if initial_balance < 0:
                errors.append("Initial balance cannot be negative.")
        except ValueError:
            errors.append("Initial balance must be a number.")
            initial_balance = 0

        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("admin/employee_form.html", mode="add", form=form, employee=None)

        user = User(
            employee_id=employee_id,
            name=name,
            mobile=mobile,
            email=email,
            status=status,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        if initial_balance > 0:
            db.session.add(
                MoneyTransaction(
                    user_id=user.id,
                    amount=initial_balance,
                    transaction_type=TRANSACTION_TYPE_CREDIT,
                    purpose="Initial Balance",
                    remarks="Opening balance set at account creation.",
                    created_by=_admin_username(),
                )
            )

        log_admin_action(
            _admin_username(), "CREATE_EMPLOYEE", target_user_id=user.id,
            detail=f"Created {user.employee_id} ({user.name})",
        )
        db.session.commit()
        flash("Employee account created successfully.", "success")
        return redirect(url_for("admin.employees"))

    return render_template("admin/employee_form.html", mode="add", form=None, employee=None)


@admin_bp.route("/employees/<int:user_id>")
@admin_required
def employee_detail(user_id):
    user = User.query.get_or_404(user_id)
    totals = get_employee_totals(user.id)
    expenses = Expense.query.filter_by(user_id=user.id).order_by(Expense.created_at.desc()).all()
    transactions = (
        MoneyTransaction.query.filter_by(user_id=user.id).order_by(MoneyTransaction.created_at.desc()).all()
    )
    return render_template(
        "admin/employee_detail.html",
        employee=user,
        totals=totals,
        expenses=expenses,
        transactions=transactions,
    )


@admin_bp.route("/employees/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_employee(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        form = request.form
        errors = []

        name = form.get("name", "").strip()
        mobile = form.get("mobile", "").strip()
        email = form.get("email", "").strip()
        status = form.get("status", user.status)

        if not name:
            errors.append("Employee name is required.")
        if not MOBILE_RE.match(mobile):
            errors.append("Enter a valid mobile number.")
        if not EMAIL_RE.match(email):
            errors.append("Enter a valid email address.")
        if status not in (STATUS_ACTIVE, STATUS_INACTIVE):
            errors.append("Invalid status.")

        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("admin/employee_form.html", mode="edit", form=form, employee=user)

        changes = []
        if user.name != name:
            changes.append(f"name: '{user.name}' -> '{name}'")
        if user.mobile != mobile:
            changes.append(f"mobile: '{user.mobile}' -> '{mobile}'")
        if user.email != email:
            changes.append(f"email: '{user.email}' -> '{email}'")
        if user.status != status:
            changes.append(f"status: '{user.status}' -> '{status}'")

        user.name = name
        user.mobile = mobile
        user.email = email
        user.status = status
        if changes:
            log_admin_action(
                _admin_username(), "EDIT_EMPLOYEE", target_user_id=user.id,
                detail="; ".join(changes),
            )
        db.session.commit()
        flash("Employee details updated successfully.", "success")
        return redirect(url_for("admin.employee_detail", user_id=user.id))

    return render_template("admin/employee_form.html", mode="edit", form=None, employee=user)


@admin_bp.route("/employees/<int:user_id>/reset-password", methods=["POST"])
@admin_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if len(new_password) < 6:
        flash("Password must be at least 6 characters.", "error")
    elif new_password != confirm_password:
        flash("Passwords do not match.", "error")
    else:
        user.set_password(new_password)
        log_admin_action(
            _admin_username(), "RESET_PASSWORD", target_user_id=user.id,
            detail=f"Password reset for {user.employee_id}",
        )
        db.session.commit()
        flash(f"Password reset successfully for {user.employee_id}.", "success")

    return redirect(url_for("admin.employee_detail", user_id=user.id))


@admin_bp.route("/employees/<int:user_id>/toggle-status", methods=["POST"])
@admin_required
def toggle_status(user_id):
    user = User.query.get_or_404(user_id)
    user.status = STATUS_INACTIVE if user.status == STATUS_ACTIVE else STATUS_ACTIVE
    log_admin_action(
        _admin_username(), "TOGGLE_STATUS", target_user_id=user.id,
        detail=f"{user.employee_id} set to {user.status}",
    )
    db.session.commit()
    flash(f"{user.name} is now {user.status}.", "success")
    return redirect(request.referrer or url_for("admin.employees"))


# ---------------------------------------------------------------------------
# Add Money
# ---------------------------------------------------------------------------

@admin_bp.route("/add-money", methods=["GET", "POST"])
@admin_required
def add_money():
    if request.method == "POST":
        form = request.form
        errors = []

        user_id = form.get("user_id", "")
        amount_raw = form.get("amount", "").strip()
        purpose = form.get("purpose", "").strip()
        remarks = form.get("remarks", "").strip()
        date_str = form.get("date", "").strip()

        user = User.query.filter_by(id=user_id).first() if user_id.isdigit() else None
        if not user:
            errors.append("Please select a valid employee.")

        try:
            amount = float(amount_raw)
            if amount <= 0:
                errors.append("Amount must be greater than ₹0.")
        except ValueError:
            errors.append("Enter a valid amount.")
            amount = 0

        if not purpose:
            errors.append("Purpose is required.")

        chosen_date = date.today()
        if date_str:
            try:
                chosen_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        if errors:
            for err in errors:
                flash(err, "error")
            return redirect(url_for("admin.add_money"))

        created_at = datetime.combine(chosen_date, datetime.now().time())
        db.session.add(
            MoneyTransaction(
                user_id=user.id,
                amount=amount,
                transaction_type=TRANSACTION_TYPE_CREDIT,
                purpose=purpose,
                remarks=remarks or None,
                created_at=created_at,
                created_by=_admin_username(),
            )
        )
        db.session.commit()
        new_balance = get_employee_balance(user.id)
        flash(f"Money added successfully. {user.name}'s new balance is {new_balance:,.2f}.", "success")
        return redirect(url_for("admin.add_money"))

    employee_list = User.query.filter_by(status=STATUS_ACTIVE).order_by(User.name).all()
    recent_transactions = (
        MoneyTransaction.query.order_by(MoneyTransaction.created_at.desc()).limit(25).all()
    )
    preselect = request.args.get("employee_id", type=int)
    return render_template(
        "admin/add_money.html",
        employees=employee_list,
        recent_transactions=recent_transactions,
        preselect=preselect,
        today=date.today().isoformat(),
    )


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

def _filter_expenses_query(args):
    query = Expense.query.join(User, Expense.user_id == User.id)

    from_date = args.get("from_date", "").strip()
    to_date = args.get("to_date", "").strip()
    employee_id = args.get("employee_id", "").strip()
    expense_type = args.get("expense_type", "").strip()
    status = args.get("status", "").strip()
    q = args.get("q", "").strip()

    if from_date:
        query = query.filter(func.date(Expense.created_at) >= from_date)
    if to_date:
        query = query.filter(func.date(Expense.created_at) <= to_date)
    if employee_id:
        query = query.filter(User.employee_id == employee_id)
    if expense_type:
        query = query.filter(Expense.expense_type == expense_type)
    if status:
        query = query.filter(Expense.payment_status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Expense.transaction_id.ilike(like),
                User.employee_id.ilike(like),
                User.name.ilike(like),
                Expense.docket_no.ilike(like),
                Expense.upi_reference_no.ilike(like),
            )
        )
    return query


@admin_bp.route("/expenses")
@admin_required
def expenses():
    query = _filter_expenses_query(request.args).order_by(Expense.created_at.desc())
    page = request.args.get("page", 1, type=int)
    pagination = query.paginate(page=page, per_page=current_app.config["ITEMS_PER_PAGE"], error_out=False)

    employee_list = User.query.order_by(User.name).all()
    return render_template(
        "admin/expenses.html",
        pagination=pagination,
        expenses=pagination.items,
        employee_list=employee_list,
        args=request.args,
    )


@admin_bp.route("/expenses/<int:expense_id>")
@admin_required
def expense_detail(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    return render_template("admin/expense_detail.html", expense=expense, back_url=url_for("admin.expenses"))


@admin_bp.route("/expenses/<int:expense_id>/invoice")
@admin_required
def expense_invoice(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    as_attachment = request.args.get("download") == "1"
    return send_from_directory(
        current_app.config["INVOICE_FOLDER"], expense.invoice_file, as_attachment=as_attachment
    )


@admin_bp.route("/expenses/<int:expense_id>/payment-screenshot")
@admin_required
def expense_screenshot(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    as_attachment = request.args.get("download") == "1"
    return send_from_directory(
        current_app.config["PAYMENT_SCREENSHOT_FOLDER"], expense.payment_screenshot, as_attachment=as_attachment
    )


# ---------------------------------------------------------------------------
# Employee-wise analytics
# ---------------------------------------------------------------------------

@admin_bp.route("/analytics")
@admin_required
def analytics():
    employee_list = User.query.order_by(User.name).all()
    selected_id = request.args.get("employee_id", type=int)
    selected = None
    totals = None
    daily_labels = daily_values = []
    logistics_total = warehousing_total = 0

    if selected_id:
        selected = User.query.get_or_404(selected_id)
        totals = get_employee_totals(selected.id)
        totals["transaction_count"] = Expense.query.filter_by(user_id=selected.id).count()
        logistics_total = totals["logistics"]
        warehousing_total = totals["warehousing"]

        rows = (
            db.session.query(func.date(Expense.created_at), func.sum(Expense.amount))
            .filter(
                Expense.user_id == selected.id,
                Expense.payment_status.in_(BALANCE_COUNTING_STATUSES),
            )
            .group_by(func.date(Expense.created_at))
            .order_by(func.date(Expense.created_at))
            .all()
        )
        daily_labels = [datetime.strptime(r[0], "%Y-%m-%d").strftime("%d %b") for r in rows]
        daily_values = [float(r[1]) for r in rows]
    else:
        ranked = []
        for u in employee_list:
            t = get_employee_totals(u.id)
            if t["spent"] > 0:
                ranked.append({"user": u, **t})
        ranked.sort(key=lambda r: r["spent"], reverse=True)
        totals = {"ranked": ranked}

    return render_template(
        "admin/analytics.html",
        employee_list=employee_list,
        selected=selected,
        totals=totals,
        daily_labels=daily_labels,
        daily_values=daily_values,
        logistics_total=logistics_total,
        warehousing_total=warehousing_total,
    )


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@admin_bp.route("/reports")
@admin_required
def reports():
    query = _filter_expenses_query(request.args).order_by(Expense.created_at.desc())
    preview = query.limit(50).all()
    total_count = query.count()
    employee_list = User.query.order_by(User.name).all()
    return render_template(
        "admin/reports.html",
        preview=preview,
        total_count=total_count,
        employee_list=employee_list,
        args=request.args,
    )


@admin_bp.route("/reports/expenses.xlsx")
@admin_required
def download_expense_report():
    query = _filter_expenses_query(request.args).order_by(Expense.created_at.desc())
    expense_list = query.all()
    from_date = request.args.get("from_date", "").strip() or None
    to_date = request.args.get("to_date", "").strip() or None

    buffer = build_expense_report(expense_list, from_date, to_date)
    label = f"{from_date or 'all'}_to_{to_date or 'all'}"
    filename = f"Final_Mile_Techies_Expense_Report_{label}.xlsx"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@admin_bp.route("/reports/money-distribution.xlsx")
@admin_required
def download_money_distribution_report():
    query = MoneyTransaction.query.join(User, MoneyTransaction.user_id == User.id)
    from_date = request.args.get("from_date", "").strip()
    to_date = request.args.get("to_date", "").strip()
    employee_id = request.args.get("employee_id", "").strip()

    if from_date:
        query = query.filter(func.date(MoneyTransaction.created_at) >= from_date)
    if to_date:
        query = query.filter(func.date(MoneyTransaction.created_at) <= to_date)
    if employee_id:
        query = query.filter(User.employee_id == employee_id)

    transactions = query.order_by(MoneyTransaction.created_at.desc()).all()
    buffer = build_money_distribution_report(transactions)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="Final_Mile_Techies_Money_Distribution_Report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------------------------------------------------------------------------
# Admin profile
# ---------------------------------------------------------------------------

@admin_bp.route("/profile")
@admin_required
def profile():
    return render_template("admin/profile.html", admin_username=_admin_username())


def _admin_username():
    from flask import session

    return session.get("username", current_app.config["ADMIN_USERNAME"])
