import secrets

from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash,
    current_app, send_from_directory,
)

from models import User
from utils.decorators import login_required

auth_bp = Blueprint("auth", __name__)


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
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        valid_username = secrets.compare_digest(username, current_app.config["ADMIN_USERNAME"])
        valid_password = secrets.compare_digest(password, current_app.config["ADMIN_PASSWORD"])

        if valid_username and valid_password:
            session.clear()
            session["role"] = "ADMIN"
            session["username"] = username
            flash("Welcome back, Admin.", "success")
            return redirect(url_for("admin.dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("auth/admin_login.html")


@auth_bp.route("/login/employee", methods=["GET", "POST"])
def employee_login():
    if session.get("role") == "EMPLOYEE":
        return redirect(url_for("employee.dashboard"))

    if request.method == "POST":
        employee_id = request.form.get("employee_id", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(employee_id=employee_id).first()

        if user and user.is_active() and user.check_password(password):
            session.clear()
            session["role"] = "EMPLOYEE"
            session["user_id"] = user.id
            session["employee_id"] = user.employee_id
            flash(f"Welcome back, {user.name}.", "success")
            return redirect(url_for("employee.dashboard"))

        flash("Invalid Employee ID or password.", "error")

    return render_template("auth/employee_login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login_select"))


@auth_bp.route("/uploads/profile-image/<path:filename>")
@login_required
def profile_image(filename):
    """Shared, login-gated route for profile photo thumbnails (admin employee
    tables and the employee's own profile page both need this)."""
    return send_from_directory(current_app.config["PROFILE_IMAGE_FOLDER"], filename)
