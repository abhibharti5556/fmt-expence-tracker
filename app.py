import os

from flask import Flask, render_template, session, g

from config import Config
from extensions import db, csrf
from utils.helpers import format_inr, get_employee_balance


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    os.makedirs(app.instance_path, exist_ok=True)
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

        sidebar_balance = None
        if session.get("role") == "EMPLOYEE" and session.get("user_id"):
            sidebar_balance = get_employee_balance(session["user_id"])

        return {
            "company_name": app.config["COMPANY_NAME"],
            "current_year": datetime.now().year,
            "session_role": session.get("role"),
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
