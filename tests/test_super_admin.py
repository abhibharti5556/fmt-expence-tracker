from extensions import db
from models import AdminUser


def _login_legacy(app, client):
    return client.post(
        "/login/admin",
        data={"email": app.config["ADMIN_USERNAME"], "password": app.config["ADMIN_PASSWORD"]},
        follow_redirects=True,
    )


def _make_regular_admin(app, name, email):
    with app.app_context():
        admin = AdminUser(name=name, email=email, status="Active", is_super_admin=False)
        admin.set_password("secret123")
        db.session.add(admin)
        db.session.commit()
        return admin.id


def test_legacy_bootstrap_session_can_create_admins(app, client):
    """Before any super admin exists, the legacy .env session is the only
    way to create the first one -- it must be treated as a super admin."""
    _login_legacy(app, client)
    resp = client.post(
        "/admin/admins/add",
        data={"name": "First Admin", "email": "first@fmt.com", "mobile": "", "password": "secret123", "confirm_password": "secret123"},
        follow_redirects=True,
    )
    assert b"created successfully" in resp.data


def test_regular_admin_cannot_create_another_admin(app, client):
    regular_id = _make_regular_admin(app, "Regular Admin", "regular@fmt.com")

    client.post("/login/admin", data={"email": "regular@fmt.com", "password": "secret123"}, follow_redirects=True)
    resp = client.get("/admin/admins")
    assert b"Add Admin" not in resp.data

    resp = client.get("/admin/admins/add", follow_redirects=True)
    assert b"Only a super admin can create new admin accounts" in resp.data

    resp = client.post(
        "/admin/admins/add",
        data={"name": "Sneaky", "email": "sneaky@fmt.com", "mobile": "", "password": "secret123", "confirm_password": "secret123"},
        follow_redirects=True,
    )
    assert b"Only a super admin can create new admin accounts" in resp.data

    with app.app_context():
        assert AdminUser.query.filter_by(email="sneaky@fmt.com").first() is None


def test_super_admin_can_create_another_admin(app, client):
    with app.app_context():
        super_admin = AdminUser(name="Super", email="super@fmt.com", status="Active", is_super_admin=True)
        super_admin.set_password("secret123")
        db.session.add(super_admin)
        db.session.commit()

    client.post("/login/admin", data={"email": "super@fmt.com", "password": "secret123"}, follow_redirects=True)
    resp = client.get("/admin/admins")
    assert b"Add Admin" in resp.data

    resp = client.post(
        "/admin/admins/add",
        data={"name": "New Admin", "email": "new@fmt.com", "mobile": "", "password": "secret123", "confirm_password": "secret123"},
        follow_redirects=True,
    )
    assert b"created successfully" in resp.data

    with app.app_context():
        created = AdminUser.query.filter_by(email="new@fmt.com").first()
        assert created is not None
        assert created.is_super_admin is False
