from extensions import db
from models import AdminUser, AdminAuditLog


def _login_legacy(app, client):
    return client.post(
        "/login/admin",
        data={"email": app.config["ADMIN_USERNAME"], "password": app.config["ADMIN_PASSWORD"]},
        follow_redirects=True,
    )


def test_legacy_env_credential_still_logs_in(app, client):
    resp = _login_legacy(app, client)
    assert resp.status_code == 200
    assert b"Dashboard" in resp.data or b"dashboard" in resp.data.lower()


def test_admin_can_create_and_login_as_new_admin(app, client):
    _login_legacy(app, client)
    resp = client.post(
        "/admin/admins/add",
        data={
            "name": "Priya Sharma", "email": "priya@fmt.com", "mobile": "9876543210",
            "password": "secret123", "confirm_password": "secret123",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"created successfully" in resp.data

    client.get("/logout")
    resp = client.post(
        "/login/admin", data={"email": "priya@fmt.com", "password": "secret123"}, follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"Priya" in resp.data


def test_duplicate_admin_email_rejected(app, client):
    _login_legacy(app, client)
    client.post(
        "/admin/admins/add",
        data={"name": "A", "email": "dupe@fmt.com", "mobile": "", "password": "secret123", "confirm_password": "secret123"},
        follow_redirects=True,
    )
    resp = client.post(
        "/admin/admins/add",
        data={"name": "B", "email": "dupe@fmt.com", "mobile": "", "password": "secret123", "confirm_password": "secret123"},
        follow_redirects=True,
    )
    assert b"already exists" in resp.data

    with app.app_context():
        assert AdminUser.query.filter_by(email="dupe@fmt.com").count() == 1


def test_inactive_admin_cannot_login(app, client):
    _login_legacy(app, client)
    client.post(
        "/admin/admins/add",
        data={"name": "Inactive Guy", "email": "inactive@fmt.com", "mobile": "", "password": "secret123", "confirm_password": "secret123"},
        follow_redirects=True,
    )
    with app.app_context():
        admin = AdminUser.query.filter_by(email="inactive@fmt.com").first()
        admin_id = admin.id
    client.post(f"/admin/admins/{admin_id}/toggle-status", follow_redirects=True)

    client.get("/logout")
    resp = client.post(
        "/login/admin", data={"email": "inactive@fmt.com", "password": "secret123"}, follow_redirects=True
    )
    assert b"Invalid email or password" in resp.data


def test_admin_cannot_deactivate_own_account(app, client):
    _login_legacy(app, client)
    client.post(
        "/admin/admins/add",
        data={"name": "Solo Admin", "email": "solo@fmt.com", "mobile": "", "password": "secret123", "confirm_password": "secret123"},
        follow_redirects=True,
    )
    client.get("/logout")
    client.post("/login/admin", data={"email": "solo@fmt.com", "password": "secret123"}, follow_redirects=True)

    with app.app_context():
        solo = AdminUser.query.filter_by(email="solo@fmt.com").first()
        solo_id = solo.id

    resp = client.post(f"/admin/admins/{solo_id}/toggle-status", follow_redirects=True)
    assert b"cannot deactivate your own account" in resp.data

    with app.app_context():
        assert AdminUser.query.get(solo_id).status == "Active"


def test_admin_can_edit_own_profile(app, client):
    _login_legacy(app, client)
    client.post(
        "/admin/admins/add",
        data={"name": "Ravi Kumar", "email": "ravi@fmt.com", "mobile": "9000000000", "password": "secret123", "confirm_password": "secret123"},
        follow_redirects=True,
    )
    client.get("/logout")
    client.post("/login/admin", data={"email": "ravi@fmt.com", "password": "secret123"}, follow_redirects=True)

    resp = client.post(
        "/admin/profile", data={"name": "Ravi K.", "mobile": "9111111111"}, follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"updated successfully" in resp.data

    with app.app_context():
        updated = AdminUser.query.filter_by(email="ravi@fmt.com").first()
        assert updated.name == "Ravi K."
        assert updated.mobile == "9111111111"


def test_admin_actions_are_logged_with_actor_name(app, client):
    _login_legacy(app, client)
    client.post(
        "/admin/admins/add",
        data={"name": "Log Test", "email": "logtest@fmt.com", "mobile": "", "password": "secret123", "confirm_password": "secret123"},
        follow_redirects=True,
    )
    with app.app_context():
        log = AdminAuditLog.query.filter_by(action="CREATE_ADMIN").order_by(AdminAuditLog.id.desc()).first()
        assert log is not None
        assert "logtest@fmt.com" in log.detail
