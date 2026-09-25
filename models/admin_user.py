from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db

from .models import STATUS_ACTIVE


class AdminUser(db.Model):
    """A person who can sign in to the admin side. Logs in with email +
    password (not the shared ADMIN_USERNAME/ADMIN_PASSWORD env credential),
    so multiple admins can each have their own account, activity trail,
    and profile."""

    __tablename__ = "admin_users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    mobile = db.Column(db.String(20), nullable=True)
    profile_image = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_ACTIVE)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def is_active(self):
        return self.status == STATUS_ACTIVE

    def __repr__(self):
        return f"<AdminUser {self.email}>"
