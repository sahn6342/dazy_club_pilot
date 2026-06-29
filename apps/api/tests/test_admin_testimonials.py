"""Admin testimonials: list, approve/reject. Auth guard."""


def test_testimonials_list_seeded(client, auth_headers):
    r = client.get("/api/v1/admin/testimonials", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) > 0


def test_testimonials_have_approved_field(client, auth_headers):
    items = client.get("/api/v1/admin/testimonials", headers=auth_headers).json()
    for item in items:
        assert "approved" in item


def test_testimonial_approve(client, auth_headers):
    items = client.get("/api/v1/admin/testimonials", headers=auth_headers).json()
    tid = items[0]["id"]
    r = client.patch(f"/api/v1/admin/testimonials/{tid}", json={"approved": True}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["approved"] is True


def test_testimonial_reject(client, auth_headers):
    items = client.get("/api/v1/admin/testimonials", headers=auth_headers).json()
    tid = items[0]["id"]
    r = client.patch(f"/api/v1/admin/testimonials/{tid}", json={"approved": False}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["approved"] is False


def test_testimonial_patch_nonexistent(client, auth_headers):
    r = client.patch("/api/v1/admin/testimonials/bad-id", json={"approved": True}, headers=auth_headers)
    assert r.status_code == 404


def test_testimonials_requires_auth(client):
    r = client.get("/api/v1/admin/testimonials")
    assert r.status_code in (401, 403)
