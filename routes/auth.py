import secrets
from urllib.parse import urlparse

from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash,
    current_app, send_from_directory,
)

from extensions import db
from models import User, AdminUser, STATUS_ACTIVE
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


def _safe_next(target):
    """Only ever redirect to a same-site relative path -- rejects anything
    with a scheme/host (open-redirect) so an emailed `next` link can't be
    abused to bounce a logged-in admin off to an attacker's site."""
    if not target or not target.startswith("/") or target.startswith("//"):
        return None
    if urlparse(target).netloc:
        return None
    return target


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
    if AdminUser.query.first() is None:
        return redirect(url_for("auth.setup"))
    return render_template("auth/login_select.html")


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """First-run only: creates the first AdminUser (as a super admin) when
    none exist yet. Permanently locks itself out the moment one is
    created -- this must never be reachable again afterward, or anyone
    who finds the URL on a live site could mint themselves a super admin
    account.

    Exists specifically so getting a working admin login doesn't depend
    on correctly configuring SUPER_ADMIN_EMAIL/PASSWORD env vars on a
    dashboard (Vercel, etc.) beforehand -- this works from a bare
    deployment with no environment setup at all."""
    if AdminUser.query.first() is not None:
        flash("Setup has already been completed. Please log in.", "info")
        return redirect(url_for("auth.login_select"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []
        if not name:
            errors.append("Name is required.")
        if not email or "@" not in email:
            errors.append("Enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm_password:
            errors.append("Passwords do not match.")

        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("auth/setup.html", form=request.form)

        # Re-check right before writing: closes the (very unlikely, but
        # SQLite's BEGIN IMMEDIATE locking doesn't fully rule out) window
        # where two people load this page before either has submitted.
        if AdminUser.query.first() is not None:
            flash("Setup has already been completed. Please log in.", "info")
            return redirect(url_for("auth.login_select"))

        admin = AdminUser(name=name, email=email, status=STATUS_ACTIVE, is_super_admin=True)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()

        session.clear()
        session.permanent = True
        session["role"] = "ADMIN"
        session["admin_id"] = admin.id
        session["username"] = admin.name
        flash(f"Welcome, {admin.name}! Your Super Admin account is ready.", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("auth/setup.html", form=None)


@auth_bp.route("/login/admin", methods=["GET", "POST"])
def admin_login():
    next_url = _safe_next(request.values.get("next"))

    if session.get("role") == "ADMIN":
        return redirect(next_url or url_for("admin.dashboard"))

    if AdminUser.query.first() is None:
        return redirect(url_for("auth.setup"))

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
            return render_template("auth/admin_login.html", next=next_url)

        admin = AdminUser.query.filter(AdminUser.email.ilike(email)).first() if email else None

        if admin and admin.is_active() and admin.check_password(password):
            record_success("ADMIN", email, ip)
            session.clear()
            session.permanent = True
            session["role"] = "ADMIN"
            session["admin_id"] = admin.id
            session["username"] = admin.name
            flash(f"Welcome back, {admin.name}.", "success")
            return redirect(next_url or url_for("admin.dashboard"))

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
            return redirect(next_url or url_for("admin.dashboard"))

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

        return render_template("auth/admin_login.html", next=next_url)

    return render_template("auth/admin_login.html", next=next_url)


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
