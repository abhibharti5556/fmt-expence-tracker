from decimal import Decimal

from models import (
    User, MoneyTransaction, Expense,
    TRANSACTION_TYPE_CREDIT, EXPENSE_TYPE_LOGISTICS, EXPENSE_TYPE_WAREHOUSING,
    PAYMENT_STATUS_SUBMITTED,
)
from utils.helpers import get_employee_balance, get_employee_totals


def _make_user(db_session, employee_id="EMP001"):
    user = User(employee_id=employee_id, name="Test User", mobile="9999999999", email="t@t.com")
    user.set_password("secret123")
    db_session.add(user)
    db_session.commit()
    return user


def test_balance_is_zero_with_no_activity(app, db_session):
    with app.app_context():
        user = _make_user(db_session)
        assert get_employee_balance(user.id) == Decimal("0")


def test_balance_reflects_credit(app, db_session):
    with app.app_context():
        user = _make_user(db_session)
        db_session.add(
            MoneyTransaction(
                user_id=user.id, amount=Decimal("1000"),
                transaction_type=TRANSACTION_TYPE_CREDIT,
                purpose="Test credit", created_by="admin",
            )
        )
        db_session.commit()
        assert get_employee_balance(user.id) == Decimal("1000")


def test_balance_subtracts_submitted_expense(app, db_session):
    with app.app_context():
        user = _make_user(db_session)
        db_session.add(
            MoneyTransaction(
                user_id=user.id, amount=Decimal("1000"),
                transaction_type=TRANSACTION_TYPE_CREDIT,
                purpose="Test credit", created_by="admin",
            )
        )
        db_session.commit()

        db_session.add(
            Expense(
                transaction_id="EXP-20260101-0001", user_id=user.id,
                expense_type=EXPENSE_TYPE_LOGISTICS, amount=Decimal("400"),
                docket_no="DK-1", purpose="Fuel", approved_by="Manager",
                upi_reference_no="REF1234", payment_status=PAYMENT_STATUS_SUBMITTED,
                invoice_file="inv.pdf", payment_screenshot="ss.png",
            )
        )
        db_session.commit()

        assert get_employee_balance(user.id) == Decimal("600")


def test_totals_split_logistics_and_warehousing(app, db_session):
    with app.app_context():
        user = _make_user(db_session)
        db_session.add(
            MoneyTransaction(
                user_id=user.id, amount=Decimal("1000"),
                transaction_type=TRANSACTION_TYPE_CREDIT,
                purpose="Credit", created_by="admin",
            )
        )
        db_session.add_all(
            [
                Expense(
                    transaction_id="EXP-20260101-0001", user_id=user.id,
                    expense_type=EXPENSE_TYPE_LOGISTICS, amount=Decimal("300"),
                    docket_no="DK-1", purpose="Fuel", approved_by="Manager",
                    upi_reference_no="REF1", payment_status=PAYMENT_STATUS_SUBMITTED,
                    invoice_file="a.pdf", payment_screenshot="a.png",
                ),
                Expense(
                    transaction_id="EXP-20260101-0002", user_id=user.id,
                    expense_type=EXPENSE_TYPE_WAREHOUSING, amount=Decimal("200"),
                    reason="Packing material", purpose="Supplies", approved_by="Manager",
                    upi_reference_no="REF2", payment_status=PAYMENT_STATUS_SUBMITTED,
                    invoice_file="b.pdf", payment_screenshot="b.png",
                ),
            ]
        )
        db_session.commit()

        totals = get_employee_totals(user.id)
        assert totals["received"] == Decimal("1000")
        assert totals["logistics"] == Decimal("300")
        assert totals["warehousing"] == Decimal("200")
        assert totals["spent"] == Decimal("500")
        assert totals["balance"] == Decimal("500")


def test_balance_ignores_other_employees(app, db_session):
    with app.app_context():
        user_a = _make_user(db_session, "EMP001")
        user_b = _make_user(db_session, "EMP002")
        db_session.add(
            MoneyTransaction(
                user_id=user_a.id, amount=Decimal("1000"),
                transaction_type=TRANSACTION_TYPE_CREDIT,
                purpose="Credit", created_by="admin",
            )
        )
        db_session.commit()

        assert get_employee_balance(user_a.id) == Decimal("1000")
        assert get_employee_balance(user_b.id) == Decimal("0")
