from functools import wraps

from flask import session, redirect, url_for, flash, abort, g

from extensions import db
from models import User


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
            flash("Please login to continue.", "info")
            return redirect(url_for("auth.login_select"))
        if session.get("role") != "ADMIN":
            abort(403)
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
