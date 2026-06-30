"""Admin testimonials: create / edit / delete (Phase 5)."""


def _create(client, headers, **over):
    payload = {"name": "Test Person", "context": "Weekend player", "quote": "Great venue!"}
    payload.update(over)
    return client.post("/api/v1/admin/testimonials", json=payload, headers=headers)


def test_create_testimonial_appears_in_list(client, auth_headers):
    r = _create(client, auth_headers, name="Riya K.")
    assert r.status_code == 201
    tid = r.json()["id"]
    rows = client.get("/api/v1/admin/testimonials", headers=auth_headers).json()
    assert any(t["id"] == tid and t["name"] == "Riya K." for t in rows)


def test_create_validation_rejects_empty(client, auth_headers):
    r = client.post("/api/v1/admin/testimonials",
                    json={"name": "", "context": "x", "quote": "y"}, headers=auth_headers)
    assert r.status_code == 422


def test_put_edits_fields(client, auth_headers):
    tid = _create(client, auth_headers).json()["id"]
    r = client.put(f"/api/v1/admin/testimonials/{tid}",
                   json={"name": "Edited Name", "quote": "Updated quote."}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Edited Name"
    assert r.json()["quote"] == "Updated quote."


def test_put_nonexistent_404(client, auth_headers):
    r = client.put("/api/v1/admin/testimonials/nope-xxx", json={"name": "X"}, headers=auth_headers)
    assert r.status_code == 404


def test_delete_removes(client, auth_headers):
    tid = _create(client, auth_headers).json()["id"]
    assert client.delete(f"/api/v1/admin/testimonials/{tid}", headers=auth_headers).status_code == 204
    rows = client.get("/api/v1/admin/testimonials", headers=auth_headers).json()
    assert all(t["id"] != tid for t in rows)


def test_delete_nonexistent_404(client, auth_headers):
    assert client.delete("/api/v1/admin/testimonials/nope-xxx", headers=auth_headers).status_code == 404


def test_approve_toggle_still_works(client, auth_headers):
    tid = _create(client, auth_headers).json()["id"]
    r = client.patch(f"/api/v1/admin/testimonials/{tid}", json={"approved": False}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["approved"] is False


def test_testimonials_crud_requires_auth(client):
    assert client.post("/api/v1/admin/testimonials", json={}).status_code in (401, 403)
    assert client.delete("/api/v1/admin/testimonials/x").status_code in (401, 403)
