from decimal import Decimal

from extensions import db
from models import User, MoneyTransaction, AdminUser, TRANSACTION_TYPE_CREDIT


def _make_employee(app, balance="50"):
    with app.app_context():
        user = User(employee_id="EMP1", name="Test Emp", mobile="9999999999", email="e@t.com")
        user.set_password("secret123")
        db.session.add(user)
        db.session.commit()
        if Decimal(balance) > 0:
            db.session.add(
                MoneyTransaction(
                    user_id=user.id, amount=Decimal(balance), transaction_type=TRANSACTION_TYPE_CREDIT,
                    purpose="seed", created_by="admin",
                )
            )
            db.session.commit()
        return user.id


def _make_admin(app, name, email, is_super_admin=False):
    with app.app_context():
        admin = AdminUser(name=name, email=email, status="Active", is_super_admin=is_super_admin)
        admin.set_password("secret123")
        db.session.add(admin)
        db.session.commit()
        return admin.id


def _login_employee(client, user_id):
    with client.session_transaction() as sess:
        sess["role"] = "EMPLOYEE"
        sess["user_id"] = user_id


def test_refill_button_hidden_when_balance_is_healthy(app, client):
    user_id = _make_employee(app, balance="500")
    _login_employee(client, user_id)
    resp = client.get("/employee/dashboard")
    assert b"Request Wallet Refill" not in resp.data


def test_refill_button_shown_when_balance_is_low(app, client):
    user_id = _make_employee(app, balance="50")
    _login_employee(client, user_id)
    resp = client.get("/employee/dashboard")
    assert b"Request Wallet Refill" in resp.data


def test_refill_request_rejected_when_balance_not_low(app, client):
    user_id = _make_employee(app, balance="500")
    _make_admin(app, "Priya Sharma", "priya@fmt.com")
    _login_employee(client, user_id)
    resp = client.post("/employee/wallet/refill-request", follow_redirects=True)
    assert b"only available when your balance is below" in resp.data


def test_refill_request_sent_and_then_rate_limited(app, client):
    user_id = _make_employee(app, balance="50")
    _make_admin(app, "Priya Sharma", "priya@fmt.com")
    _login_employee(client, user_id)

    resp = client.post("/employee/wallet/refill-request", follow_redirects=True)
    assert b"Refill request sent" in resp.data

    with app.app_context():
        user = User.query.get(user_id)
        assert user.last_refill_request_at is not None

    resp = client.post("/employee/wallet/refill-request", follow_redirects=True)
    assert b"already requested a refill recently" in resp.data

    resp = client.get("/employee/dashboard")
    assert b"already requested" in resp.data.lower()


def test_refill_request_excludes_super_admin_recipient(app, client, monkeypatch):
    user_id = _make_employee(app, balance="50")
    _make_admin(app, "Priya Sharma", "priya@fmt.com", is_super_admin=False)
    _make_admin(app, "Super Boss", "super@fmt.com", is_super_admin=True)
    _login_employee(client, user_id)

    captured = {}

    def fake_send(user, admins, balance, recent_expenses):
        captured["emails"] = [a.email for a in admins]
        return True

    import routes.employee as employee_routes
    monkeypatch.setattr(employee_routes, "send_wallet_refill_request", fake_send)

    client.post("/employee/wallet/refill-request", follow_redirects=True)

    assert captured["emails"] == ["priya@fmt.com"]
