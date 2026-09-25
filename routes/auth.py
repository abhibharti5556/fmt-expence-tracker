import secrets

from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash,
    current_app, send_from_directory,
)

from models import User, AdminUser
from utils.decorators import login_required
from utils.helpers import delete_uploaded_file
from utils.rate_limit import is_locked_out, record_failure, record_success

auth_bp = Blueprint("auth", __name__)


def _lockout_config():
    return (
        current_app.config["LOGIN_MAX_ATTEMPTS"],
        current_app.config["LOGIN_ATTEMPT_WINDOW_MINUTES"],
        current_app.config["LOGIN_LOCKOUT_MINUTES"],
    )


def _client_ip():
    return request.remote_addr or "unknown"


@auth_bp.route("/")
def index():
    if session.get("role") == "ADMIN":
        return redirect(url_for("admin.dashboard"))
    if session.get("role") == "EMPLOYEE":
        return redirect(url_for("employee.dashboard"))
    return redirect(url_for("auth.login_select"))


@auth_bp.route("/login")
def login_select():
    if session.get("role") == "ADMIN":
        return redirect(url_for("admin.dashboard"))
    if session.get("role") == "EMPLOYEE":
        return redirect(url_for("employee.dashboard"))
    return render_template("auth/login_select.html")


@auth_bp.route("/login/admin", methods=["GET", "POST"])
def admin_login():
    if session.get("role") == "ADMIN":
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        ip = _client_ip()

        remaining = is_locked_out("ADMIN", email or "admin", ip)
        if remaining is not None:
            flash(
                f"Too many failed attempts. Try again in {int(remaining // 60) + 1} minute(s).",
                "error",
            )
            return render_template("auth/admin_login.html")

        admin = AdminUser.query.filter(AdminUser.email.ilike(email)).first() if email else None

        if admin and admin.is_active() and admin.check_password(password):
            record_success("ADMIN", email, ip)
            session.clear()
            session.permanent = True
            session["role"] = "ADMIN"
            session["admin_id"] = admin.id
            session["username"] = admin.name
            flash(f"Welcome back, {admin.name}.", "success")
            return redirect(url_for("admin.dashboard"))

        # Bootstrap path: lets the very first admin account be created via
        # the "Manage Admins" screen before any AdminUser rows exist yet.
        # Drop this once real admin accounts are confirmed working.
        valid_username = secrets.compare_digest(email, current_app.config["ADMIN_USERNAME"])
        valid_password = secrets.compare_digest(password, current_app.config["ADMIN_PASSWORD"])
        if valid_username and valid_password:
            record_success("ADMIN", email, ip)
            session.clear()
            session.permanent = True
            session["role"] = "ADMIN"
            session["username"] = email
            flash("Welcome back, Admin.", "success")
            return redirect(url_for("admin.dashboard"))

        max_attempts, window_minutes, lockout_minutes = _lockout_config()
        locked = record_failure(
            "ADMIN", email or "admin", ip, max_attempts, window_minutes, lockout_minutes
        )
        if locked:
            flash(
                f"Too many failed attempts. Try again in {lockout_minutes} minute(s).", "error"
            )
        else:
            flash("Invalid email or password.", "error")

    return render_template("auth/admin_login.html")


@auth_bp.route("/login/employee", methods=["GET", "POST"])
def employee_login():
    if session.get("role") == "EMPLOYEE":
        return redirect(url_for("employee.dashboard"))

    if request.method == "POST":
        employee_id = request.form.get("employee_id", "").strip()
        password = request.form.get("password", "")
        ip = _client_ip()

        remaining = is_locked_out("EMPLOYEE", employee_id or "unknown", ip)
        if remaining is not None:
            flash(
                f"Too many failed attempts. Try again in {int(remaining // 60) + 1} minute(s).",
                "error",
            )
            return render_template("auth/employee_login.html")

        user = User.query.filter_by(employee_id=employee_id).first()

        if user and user.is_active() and user.check_password(password):
            record_success("EMPLOYEE", employee_id, ip)
            session.clear()
            session.permanent = True
            session["role"] = "EMPLOYEE"
            session["user_id"] = user.id
            session["employee_id"] = user.employee_id
            flash(f"Welcome back, {user.name}.", "success")
            return redirect(url_for("employee.dashboard"))

        max_attempts, window_minutes, lockout_minutes = _lockout_config()
        locked = record_failure(
            "EMPLOYEE", employee_id or "unknown", ip, max_attempts, window_minutes, lockout_minutes
        )
        if locked:
            flash(
                f"Too many failed attempts. Try again in {lockout_minutes} minute(s).", "error"
            )
        else:
            flash("Invalid Employee ID or password.", "error")

    return render_template("auth/employee_login.html")


@auth_bp.route("/logout")
def logout():
    draft = session.get("expense_draft")
    if draft and draft.get("invoice_file"):
        delete_uploaded_file(current_app.config["INVOICE_FOLDER"], draft["invoice_file"])
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login_select"))


@auth_bp.route("/uploads/profile-image/<path:filename>")
@login_required
def profile_image(filename):
    """Shared, login-gated route for profile photo thumbnails (admin employee
    tables and the employee's own profile page both need this)."""
    return send_from_directory(current_app.config["PROFILE_IMAGE_FOLDER"], filename)
