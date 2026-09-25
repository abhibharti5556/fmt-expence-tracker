from decimal import Decimal

from extensions import db
from models import (
    User, MoneyTransaction, Expense,
    TRANSACTION_TYPE_CREDIT, EXPENSE_TYPE_LOGISTICS,
    PAYMENT_STATUS_PENDING_APPROVAL, PAYMENT_STATUS_APPROVED, PAYMENT_STATUS_REJECTED,
)
from utils.helpers import get_employee_balance


def _make_user(db_session, employee_id="EMP001"):
    user = User(employee_id=employee_id, name="Test User", mobile="9999999999", email="t@t.com")
    user.set_password("secret123")
    db_session.add(user)
    db_session.commit()
    return user


def _credit(db_session, user, amount):
    db_session.add(
        MoneyTransaction(
            user_id=user.id, amount=Decimal(amount),
            transaction_type=TRANSACTION_TYPE_CREDIT,
            purpose="Test credit", created_by="admin",
        )
    )
    db_session.commit()


def _logistics_expense(user, status, txn="EXP-20260101-0001", amount="400"):
    return Expense(
        transaction_id=txn, user_id=user.id,
        expense_type=EXPENSE_TYPE_LOGISTICS, amount=Decimal(amount),
        docket_no="DK-1", category="Loading", purpose="Loading", approved_by="Manager",
        upi_reference_no="REF1234", payment_status=status,
        invoice_file="inv.pdf", payment_screenshot="ss.png",
    )


def test_pending_approval_expense_reserves_balance_immediately(app, db_session):
    with app.app_context():
        user = _make_user(db_session)
        _credit(db_session, user, "1000")
        db_session.add(_logistics_expense(user, PAYMENT_STATUS_PENDING_APPROVAL))
        db_session.commit()

        assert get_employee_balance(user.id) == Decimal("600")


def test_approved_expense_stays_counted_against_balance(app, db_session):
    with app.app_context():
        user = _make_user(db_session)
        _credit(db_session, user, "1000")
        db_session.add(_logistics_expense(user, PAYMENT_STATUS_APPROVED))
        db_session.commit()

        assert get_employee_balance(user.id) == Decimal("600")


def test_rejected_expense_is_excluded_from_balance(app, db_session):
    with app.app_context():
        user = _make_user(db_session)
        _credit(db_session, user, "1000")
        db_session.add(_logistics_expense(user, PAYMENT_STATUS_REJECTED))
        db_session.commit()

        assert get_employee_balance(user.id) == Decimal("1000")


def test_expense_stores_category(app, db_session):
    with app.app_context():
        user = _make_user(db_session)
        expense = _logistics_expense(user, PAYMENT_STATUS_PENDING_APPROVAL)
        db_session.add(expense)
        db_session.commit()

        assert Expense.query.get(expense.id).category == "Loading"


def _login_admin(client):
    with client.session_transaction() as sess:
        sess["role"] = "ADMIN"
        sess["username"] = "admin"


def test_admin_can_approve_pending_expense(app, client):
    with app.app_context():
        user = _make_user(db.session)
        expense = _logistics_expense(user, PAYMENT_STATUS_PENDING_APPROVAL)
        db.session.add(expense)
        db.session.commit()
        expense_id = expense.id

        _login_admin(client)
        resp = client.post(f"/admin/expenses/{expense_id}/approve", follow_redirects=True)
        assert resp.status_code == 200
        assert Expense.query.get(expense_id).payment_status == PAYMENT_STATUS_APPROVED


def test_admin_reject_requires_a_reason(app, client):
    with app.app_context():
        user = _make_user(db.session)
        expense = _logistics_expense(user, PAYMENT_STATUS_PENDING_APPROVAL)
        db.session.add(expense)
        db.session.commit()
        expense_id = expense.id

        _login_admin(client)
        resp = client.post(f"/admin/expenses/{expense_id}/reject", data={"rejection_reason": ""}, follow_redirects=True)
        assert resp.status_code == 200
        assert Expense.query.get(expense_id).payment_status == PAYMENT_STATUS_PENDING_APPROVAL


def test_admin_reject_with_reason_excludes_expense_from_balance(app, client):
    with app.app_context():
        user = _make_user(db.session)
        _credit(db.session, user, "1000")
        expense = _logistics_expense(user, PAYMENT_STATUS_PENDING_APPROVAL)
        db.session.add(expense)
        db.session.commit()
        expense_id = expense.id
        user_id = user.id

        _login_admin(client)
        resp = client.post(
            f"/admin/expenses/{expense_id}/reject",
            data={"rejection_reason": "Missing invoice detail"},
            follow_redirects=True,
        )
        assert resp.status_code == 200

        expense = Expense.query.get(expense_id)
        assert expense.payment_status == PAYMENT_STATUS_REJECTED
        assert expense.rejection_reason == "Missing invoice detail"
        assert get_employee_balance(user_id) == Decimal("1000")


def test_cannot_approve_an_already_decided_expense(app, client):
    with app.app_context():
        user = _make_user(db.session)
        expense = _logistics_expense(user, PAYMENT_STATUS_APPROVED)
        db.session.add(expense)
        db.session.commit()
        expense_id = expense.id

        _login_admin(client)
        resp = client.post(f"/admin/expenses/{expense_id}/approve", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Only expenses awaiting approval" in resp.data
