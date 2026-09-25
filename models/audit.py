from datetime import datetime

from extensions import db


class AdminAuditLog(db.Model):
    """Who (which admin) did what to which employee, and when. Covers the
    actions that aren't already traceable another way — money credits
    already carry `created_by` on MoneyTransaction, so those aren't
    duplicated here."""

    __tablename__ = "admin_audit_log"

    id = db.Column(db.Integer, primary_key=True)
    admin_username = db.Column(db.String(120), nullable=False)
    action = db.Column(db.String(60), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    detail = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    target_user = db.relationship("User", foreign_keys=[target_user_id])


def log_admin_action(admin_username, action, target_user_id=None, detail=None):
    db.session.add(
        AdminAuditLog(
            admin_username=admin_username,
            action=action,
            target_user_id=target_user_id,
            detail=detail,
        )
    )
