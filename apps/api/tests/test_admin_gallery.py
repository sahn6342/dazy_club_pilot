"""Admin gallery: list, approve/reject, delete. Auth guard."""


def test_gallery_list_seeded(client, auth_headers):
    r = client.get("/api/v1/admin/gallery", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()
    assert len(items) > 0


def test_gallery_items_have_approved_field(client, auth_headers):
    items = client.get("/api/v1/admin/gallery", headers=auth_headers).json()
    for item in items:
        assert "approved" in item


def test_gallery_approve_item(client, auth_headers):
    items = client.get("/api/v1/admin/gallery", headers=auth_headers).json()
    item_id = items[0]["id"]
    r = client.patch(f"/api/v1/admin/gallery/{item_id}", json={"approved": True}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["approved"] is True


def test_gallery_reject_item(client, auth_headers):
    items = client.get("/api/v1/admin/gallery", headers=auth_headers).json()
    item_id = items[0]["id"]
    r = client.patch(f"/api/v1/admin/gallery/{item_id}", json={"approved": False}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["approved"] is False


def test_gallery_delete_item(client, auth_headers):
    items = client.get("/api/v1/admin/gallery", headers=auth_headers).json()
    count_before = len(items)
    item_id = items[0]["id"]
    r = client.delete(f"/api/v1/admin/gallery/{item_id}", headers=auth_headers)
    assert r.status_code == 204
    items_after = client.get("/api/v1/admin/gallery", headers=auth_headers).json()
    assert len(items_after) == count_before - 1


def test_gallery_delete_nonexistent(client, auth_headers):
    r = client.delete("/api/v1/admin/gallery/fake-id-xxx", headers=auth_headers)
    assert r.status_code == 404


def test_gallery_patch_nonexistent(client, auth_headers):
    r = client.patch("/api/v1/admin/gallery/fake-id-xxx", json={"approved": True}, headers=auth_headers)
    assert r.status_code == 404


def test_gallery_requires_auth(client):
    r = client.get("/api/v1/admin/gallery")
    assert r.status_code in (401, 403)
