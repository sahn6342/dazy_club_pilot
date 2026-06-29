"""Admin user management: create/list/update/delete managers. Superadmin-only."""


def test_list_users_empty(client, auth_headers):
    r = client.get("/api/v1/admin/users", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_create_manager(client, auth_headers):
    r = client.post("/api/v1/admin/users", json={"username": "mgr1", "password": "secure123"}, headers=auth_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "mgr1"
    assert body["role"] == "manager"
    assert "id" in body
    assert "hashed_password" not in body


def test_list_users_after_create(client, auth_headers):
    client.post("/api/v1/admin/users", json={"username": "mgr1", "password": "secure123"}, headers=auth_headers)
    r = client.get("/api/v1/admin/users", headers=auth_headers)
    assert len(r.json()) == 1


def test_duplicate_username_rejected(client, auth_headers):
    client.post("/api/v1/admin/users", json={"username": "mgr1", "password": "secure123"}, headers=auth_headers)
    r = client.post("/api/v1/admin/users", json={"username": "mgr1", "password": "secure456"}, headers=auth_headers)
    assert r.status_code == 409


def test_password_too_short(client, auth_headers):
    r = client.post("/api/v1/admin/users", json={"username": "mgr1", "password": "short"}, headers=auth_headers)
    assert r.status_code == 422


def test_username_too_short(client, auth_headers):
    r = client.post("/api/v1/admin/users", json={"username": "ab", "password": "secure123"}, headers=auth_headers)
    assert r.status_code == 422


def test_cannot_create_admin_role(client, auth_headers):
    r = client.post("/api/v1/admin/users", json={"username": "mgr1", "password": "secure123", "role": "admin"}, headers=auth_headers)
    assert r.status_code == 422


def test_update_manager_password(client, auth_headers):
    client.post("/api/v1/admin/users", json={"username": "mgr1", "password": "secure123"}, headers=auth_headers)
    user = client.get("/api/v1/admin/users", headers=auth_headers).json()[0]
    r = client.patch(f"/api/v1/admin/users/{user['id']}", json={"password": "newsecure99"}, headers=auth_headers)
    assert r.status_code == 200
    # New password works for login
    login = client.post("/api/v1/admin/login", json={"username": "mgr1", "password": "newsecure99"})
    assert login.status_code == 200


def test_delete_manager(client, auth_headers):
    client.post("/api/v1/admin/users", json={"username": "mgr1", "password": "secure123"}, headers=auth_headers)
    user = client.get("/api/v1/admin/users", headers=auth_headers).json()[0]
    r = client.delete(f"/api/v1/admin/users/{user['id']}", headers=auth_headers)
    assert r.status_code == 204
    assert client.get("/api/v1/admin/users", headers=auth_headers).json() == []


def test_delete_nonexistent_user(client, auth_headers):
    r = client.delete("/api/v1/admin/users/fake-id-xxx", headers=auth_headers)
    assert r.status_code == 404


def test_manager_cannot_manage_users(client, auth_headers):
    client.post("/api/v1/admin/users", json={"username": "mgr1", "password": "secure123"}, headers=auth_headers)
    mgr_token = client.post("/api/v1/admin/login", json={"username": "mgr1", "password": "secure123"}).json()["access_token"]
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
    r = client.get("/api/v1/admin/users", headers=mgr_headers)
    assert r.status_code == 403


def test_manager_can_access_bookings(client, auth_headers):
    client.post("/api/v1/admin/users", json={"username": "mgr1", "password": "secure123"}, headers=auth_headers)
    mgr_token = client.post("/api/v1/admin/login", json={"username": "mgr1", "password": "secure123"}).json()["access_token"]
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
    r = client.get("/api/v1/admin/bookings", headers=mgr_headers)
    assert r.status_code == 200


def test_users_endpoint_requires_auth(client):
    r = client.get("/api/v1/admin/users")
    assert r.status_code in (401, 403)
