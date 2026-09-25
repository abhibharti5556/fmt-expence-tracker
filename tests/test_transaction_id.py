from datetime import date
from decimal import Decimal

from models import User, Expense, EXPENSE_TYPE_LOGISTICS, PAYMENT_STATUS_SUBMITTED
from utils.helpers import generate_transaction_id


def _make_user(db_session):
    user = User(employee_id="EMP001", name="Test User", mobile="9999999999", email="t@t.com")
    user.set_password("secret123")
    db_session.add(user)
    db_session.commit()
    return user


def _make_expense(db_session, user_id, transaction_id):
    db_session.add(
        Expense(
            transaction_id=transaction_id, user_id=user_id,
            expense_type=EXPENSE_TYPE_LOGISTICS, amount=Decimal("100"),
            docket_no=f"DK-{transaction_id}", purpose="Fuel", approved_by="Manager",
            upi_reference_no="REF1234", payment_status=PAYMENT_STATUS_SUBMITTED,
            invoice_file="inv.pdf", payment_screenshot="ss.png",
        )
    )
    db_session.commit()


def test_first_transaction_id_of_the_day(app, db_session):
    with app.app_context():
        today_str = date.today().strftime("%Y%m%d")
        txn_id = generate_transaction_id()
        assert txn_id == f"EXP-{today_str}-0001"


def test_sequence_increments_within_the_day(app, db_session):
    with app.app_context():
        user = _make_user(db_session)
        today_str = date.today().strftime("%Y%m%d")

        first = generate_transaction_id()
        _make_expense(db_session, user.id, first)

        second = generate_transaction_id()
        assert second == f"EXP-{today_str}-0002"


def test_never_returns_a_duplicate_of_an_existing_id(app, db_session):
    with app.app_context():
        user = _make_user(db_session)
        today_str = date.today().strftime("%Y%m%d")

        # Simulate a gap: 0001 exists, but a later ID (0003) was also
        # already taken (e.g. from a retried collision). The generator
        # must still skip both, not just naively return count+1.
        _make_expense(db_session, user.id, f"EXP-{today_str}-0001")
        _make_expense(db_session, user.id, f"EXP-{today_str}-0003")

        # count_today is 2, so the naive guess would be 0003 -- already
        # taken. The retry-on-collision loop must skip past it to 0004.
        new_id = generate_transaction_id()
        assert new_id == f"EXP-{today_str}-0004"
        assert Expense.query.filter_by(transaction_id=new_id).first() is None
