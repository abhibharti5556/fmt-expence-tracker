from functools import wraps

from flask import session, redirect, url_for, flash, abort, g, request

from extensions import db
from models import User, AdminUser


def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("role"):
            flash("Please login to continue.", "info")
            return redirect(url_for("auth.login_select"))
        return f(*args, **kwargs)

    return wrapped


def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("role"):
            # Straight to admin login (not the role picker) with a `next`
            # so an emailed deep link (e.g. "review this expense") lands
            # the admin back on the exact page after they sign in.
            return redirect(url_for("auth.admin_login", next=request.path))
        if session.get("role") != "ADMIN":
            abort(403)
        # `admin_id` is only set for accounts created in the admin_users
        # table. Sessions from the legacy env-credential login (kept as a
        # bootstrap path until real admin accounts are confirmed working)
        # have no admin_id and skip this re-check.
        admin_id = session.get("admin_id")
        if admin_id:
            admin = db.session.get(AdminUser, admin_id)
            if admin is None or not admin.is_active():
                session.clear()
                flash("Your admin account is not available. Please contact another Admin.", "error")
                return redirect(url_for("auth.login_select"))
            g.current_admin = admin
        return f(*args, **kwargs)

    return wrapped


def employee_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("role"):
            flash("Please login to continue.", "info")
            return redirect(url_for("auth.login_select"))
        if session.get("role") != "EMPLOYEE":
            abort(403)
        user = db.session.get(User, session.get("user_id"))
        if user is None or not user.is_active():
            session.clear()
            flash("Your account is not available. Please contact Admin.", "error")
            return redirect(url_for("auth.login_select"))
        g.current_user = user
        return f(*args, **kwargs)

    return wrapped


def current_employee():
    return getattr(g, "current_user", None)


def current_admin():
    """The logged-in AdminUser row, or None for a legacy env-credential
    session that has no database account behind it."""
    return getattr(g, "current_admin", None)
