"""Auth: login validation, JWT issuance, token rejection."""


def test_login_superadmin_success(client):
    r = client.post("/api/v1/admin/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password(client):
    r = client.post("/api/v1/admin/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_wrong_username(client):
    r = client.post("/api/v1/admin/login", json={"username": "ghost", "password": "admin"})
    assert r.status_code == 401


def test_login_empty_fields(client):
    r = client.post("/api/v1/admin/login", json={"username": "", "password": ""})
    assert r.status_code == 422


def test_protected_route_no_token(client):
    r = client.get("/api/v1/admin/bookings")
    assert r.status_code in (401, 403)


def test_protected_route_bad_token(client):
    r = client.get("/api/v1/admin/bookings", headers={"Authorization": "Bearer totallyinvalid"})
    assert r.status_code == 401


def test_login_manager_success(client, auth_headers):
    client.post("/api/v1/admin/users", json={"username": "mgr1", "password": "secure123"}, headers=auth_headers)
    r = client.post("/api/v1/admin/login", json={"username": "mgr1", "password": "secure123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_manager_wrong_password(client, auth_headers):
    client.post("/api/v1/admin/users", json={"username": "mgr2", "password": "secure123"}, headers=auth_headers)
    r = client.post("/api/v1/admin/login", json={"username": "mgr2", "password": "badpass"})
    assert r.status_code == 401
