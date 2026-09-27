import os

from flask import Flask, render_template, session, g
from sqlalchemy import event

from config import Config, IS_VERCEL
from extensions import db, csrf
from utils.helpers import format_inr, get_employee_balance


def _configure_sqlite_locking(app):
    """Make every DB transaction take SQLite's write lock (BEGIN IMMEDIATE)
    as soon as it starts, instead of only when the first write happens.

    Without this, a request can read an employee's balance, decide an
    expense fits, and only acquire the write lock later when it inserts
    the Expense row. Two concurrent requests can both pass that read
    before either writes, letting an employee's balance go negative.
    SQLite serializes writers anyway (single-writer lock), so forcing the
    lock to be taken at the start of the transaction closes that gap
    without needing app-level locking. Readers are unaffected — an
    IMMEDIATE transaction only blocks other writers, not other readers.
    """

    with app.app_context():

        @event.listens_for(db.engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, connection_record):
            dbapi_connection.isolation_level = None
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA busy_timeout = 5000")
            cursor.close()

        @event.listens_for(db.engine, "begin")
        def _begin_immediate(conn):
            conn.exec_driver_sql("BEGIN IMMEDIATE")


def create_app(test_config=None):
    """`test_config`, if given, is applied after the normal Config object
    and can override anything (DB URI, upload folders, etc.) — used by the
    test suite to point at an isolated temp DB instead of the real one in
    instance/. Normal usage (`create_app()`) is unaffected."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    if not IS_VERCEL:
        os.makedirs(app.instance_path, exist_ok=True)

    if test_config:
        app.config.update(test_config)

    if "SQLALCHEMY_DATABASE_URI" not in app.config:
        if IS_VERCEL:
            # /tmp only -- see the IS_VERCEL note in config.py. Every cold
            # start may see an empty database; this is a demo accommodation,
            # not persistence.
            app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////tmp/expenses.db"
        else:
            app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
                app.instance_path, "expenses.db"
            )

    for folder in (
        Config.PROFILE_IMAGE_FOLDER,
        Config.INVOICE_FOLDER,
        Config.PAYMENT_SCREENSHOT_FOLDER,
    ):
        os.makedirs(folder, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)
    _configure_sqlite_locking(app)

    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.employee import employee_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(employee_bp)

    app.jinja_env.filters["inr"] = format_inr

    @app.context_processor
    def inject_globals():
        from datetime import datetime
        from utils.decorators import current_admin
        from utils.helpers import get_pending_approvals_count

        sidebar_balance = None
        if session.get("role") == "EMPLOYEE" and session.get("user_id"):
            sidebar_balance = get_employee_balance(session["user_id"])

        sidebar_pending_approvals = None
        if session.get("role") == "ADMIN":
            sidebar_pending_approvals = get_pending_approvals_count(current_admin())

        return {
            "company_name": app.config["COMPANY_NAME"],
            "current_year": datetime.now().year,
            "session_role": session.get("role"),
            "sidebar_pending_approvals": sidebar_pending_approvals,
            "sidebar_balance": sidebar_balance,
        }

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    with app.app_context():
        db.create_all()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=app.config["FLASK_DEBUG"])
