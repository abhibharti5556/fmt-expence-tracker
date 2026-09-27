import io
from decimal import Decimal

from PIL import Image

from extensions import db
from models import (
    User, MoneyTransaction, Expense, AdminUser,
    TRANSACTION_TYPE_CREDIT, EXPENSE_TYPE_WAREHOUSING,
    PAYMENT_STATUS_PENDING_APPROVAL, PAYMENT_STATUS_APPROVED,
)


def _pdf():
    return (io.BytesIO(b"%PDF-1.4\n%fake"), "invoice.pdf")


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="PNG")
    buf.seek(0)
    return (buf, "ss.png")


def _make_employee_with_balance(app, amount="1000"):
    with app.app_context():
        user = User(employee_id="EMP1", name="Test Emp", mobile="9999999999", email="e@t.com")
        user.set_password("secret123")
        db.session.add(user)
        db.session.commit()
        db.session.add(
            MoneyTransaction(
                user_id=user.id, amount=Decimal(amount), transaction_type=TRANSACTION_TYPE_CREDIT,
                purpose="seed", created_by="admin",
            )
        )
        db.session.commit()
        return user.id


def _make_admin(app, name, email):
    with app.app_context():
        admin = AdminUser(name=name, email=email, status="Active")
        admin.set_password("secret123")
        db.session.add(admin)
        db.session.commit()
        return admin.id


def _submit_warehousing_expense(client, assigned_admin_id):
    client.post(
        "/employee/expense/new/warehousing",
        data={
            "amount": "250", "category": "Pantry", "purpose": "Tea and coffee",
            "reason": "Monthly stock", "approved_by": str(assigned_admin_id), "remarks": "",
            "invoice": _pdf(),
        },
        content_type="multipart/form-data", follow_redirects=True,
    )
    client.get("/employee/expense/pay")
    return client.post(
        "/employee/expense/confirm",
        data={"upi_reference_no": "REF999888", "payment_screenshot": _png()},
        content_type="multipart/form-data", follow_redirects=True,
    )


def test_warehousing_expense_now_requires_approval(app, client):
    user_id = _make_employee_with_balance(app)
    admin_id = _make_admin(app, "Alice Admin", "alice@fmt.com")

    with client.session_transaction() as sess:
        sess["role"] = "EMPLOYEE"
        sess["user_id"] = user_id

    resp = _submit_warehousing_expense(client, admin_id)
    assert resp.status_code == 200
    assert b"Submitted Successfully" in resp.data

    with app.app_context():
        expense = Expense.query.filter_by(expense_type=EXPENSE_TYPE_WAREHOUSING).first()
        assert expense.payment_status == PAYMENT_STATUS_PENDING_APPROVAL
        assert expense.assigned_admin_id == admin_id


def test_only_assigned_admin_can_approve(app, client):
    user_id = _make_employee_with_balance(app)
    alice_id = _make_admin(app, "Alice Admin", "alice@fmt.com")
    _make_admin(app, "Bob Admin", "bob@fmt.com")

    with client.session_transaction() as sess:
        sess["role"] = "EMPLOYEE"
        sess["user_id"] = user_id
    _submit_warehousing_expense(client, alice_id)
    client.get("/logout")

    with app.app_context():
        expense_id = Expense.query.first().id

    client.post("/login/admin", data={"email": "bob@fmt.com", "password": "secret123"}, follow_redirects=True)
    resp = client.post(f"/admin/expenses/{expense_id}/approve", follow_redirects=True)
    assert b"Only Alice Admin can approve" in resp.data

    with app.app_context():
        assert Expense.query.get(expense_id).payment_status == PAYMENT_STATUS_PENDING_APPROVAL

    client.get("/logout")
    client.post("/login/admin", data={"email": "alice@fmt.com", "password": "secret123"}, follow_redirects=True)
    resp = client.post(f"/admin/expenses/{expense_id}/approve", follow_redirects=True)
    assert b"approved" in resp.data.lower()

    with app.app_context():
        assert Expense.query.get(expense_id).payment_status == PAYMENT_STATUS_APPROVED


def test_deep_link_redirects_through_admin_login_and_back(app, client):
    user_id = _make_employee_with_balance(app)
    alice_id = _make_admin(app, "Alice Admin", "alice@fmt.com")

    with client.session_transaction() as sess:
        sess["role"] = "EMPLOYEE"
        sess["user_id"] = user_id
    _submit_warehousing_expense(client, alice_id)
    client.get("/logout")

    with app.app_context():
        expense_id = Expense.query.first().id

    resp = client.get(f"/admin/expenses/{expense_id}", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"] == f"/login/admin?next=/admin/expenses/{expense_id}"

    resp = client.post(
        "/login/admin",
        data={"email": "alice@fmt.com", "password": "secret123", "next": f"/admin/expenses/{expense_id}"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Awaiting Your Approval" in resp.data


def test_one_click_approve_link_works_via_get(app, client):
    """The email's Approve button is a plain <a href> -- email clients
    don't submit forms, so this must work as a GET, not just POST."""
    user_id = _make_employee_with_balance(app)
    alice_id = _make_admin(app, "Alice Admin", "alice@fmt.com")

    with client.session_transaction() as sess:
        sess["role"] = "EMPLOYEE"
        sess["user_id"] = user_id
    _submit_warehousing_expense(client, alice_id)
    client.get("/logout")

    with app.app_context():
        expense_id = Expense.query.first().id

    client.post("/login/admin", data={"email": "alice@fmt.com", "password": "secret123"}, follow_redirects=True)
    resp = client.get(f"/admin/expenses/{expense_id}/approve", follow_redirects=True)
    assert b"approved" in resp.data.lower()

    with app.app_context():
        assert Expense.query.get(expense_id).payment_status == PAYMENT_STATUS_APPROVED


def test_approve_link_clicked_twice_is_a_no_op(app, client):
    user_id = _make_employee_with_balance(app)
    alice_id = _make_admin(app, "Alice Admin", "alice@fmt.com")

    with client.session_transaction() as sess:
        sess["role"] = "EMPLOYEE"
        sess["user_id"] = user_id
    _submit_warehousing_expense(client, alice_id)
    client.get("/logout")

    with app.app_context():
        expense_id = Expense.query.first().id

    client.post("/login/admin", data={"email": "alice@fmt.com", "password": "secret123"}, follow_redirects=True)
    client.get(f"/admin/expenses/{expense_id}/approve", follow_redirects=True)
    resp = client.get(f"/admin/expenses/{expense_id}/approve", follow_redirects=True)
    assert b"already approved" in resp.data.lower()

    with app.app_context():
        assert Expense.query.get(expense_id).payment_status == PAYMENT_STATUS_APPROVED


def test_approve_link_while_logged_out_bounces_through_login_then_approves(app, client):
    user_id = _make_employee_with_balance(app)
    alice_id = _make_admin(app, "Alice Admin", "alice@fmt.com")

    with client.session_transaction() as sess:
        sess["role"] = "EMPLOYEE"
        sess["user_id"] = user_id
    _submit_warehousing_expense(client, alice_id)
    client.get("/logout")

    with app.app_context():
        expense_id = Expense.query.first().id

    resp = client.get(f"/admin/expenses/{expense_id}/approve", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"] == f"/login/admin?next=/admin/expenses/{expense_id}/approve"

    resp = client.post(
        "/login/admin",
        data={"email": "alice@fmt.com", "password": "secret123", "next": f"/admin/expenses/{expense_id}/approve"},
        follow_redirects=True,
    )
    assert b"approved" in resp.data.lower()

    with app.app_context():
        assert Expense.query.get(expense_id).payment_status == PAYMENT_STATUS_APPROVED


def test_next_redirect_rejects_external_url(app, client):
    _make_admin(app, "Alice Admin", "alice@fmt.com")
    resp = client.post(
        "/login/admin",
        data={"email": "alice@fmt.com", "password": "secret123", "next": "https://evil.example.com/steal"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/admin/dashboard"
