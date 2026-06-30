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


# ── Phase 5: imageUrl + upload + DB-driven public route ───────────────────────

def test_gallery_items_have_image_url(client, auth_headers):
    items = client.get("/api/v1/admin/gallery", headers=auth_headers).json()
    for item in items:
        assert "imageUrl" in item


def test_gallery_create_with_image_url(client, auth_headers):
    r = client.post("/api/v1/admin/gallery", json={
        "title": "New action shot", "sportSlug": "cricket", "tone": "electric",
        "imageUrl": "https://example.com/pic.jpg", "approved": True,
    }, headers=auth_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["imageUrl"] == "https://example.com/pic.jpg"
    assert body["title"] == "New action shot"


def test_gallery_patch_image_and_fields(client, auth_headers):
    item_id = client.get("/api/v1/admin/gallery", headers=auth_headers).json()[0]["id"]
    r = client.patch(f"/api/v1/admin/gallery/{item_id}", json={
        "title": "Edited title", "tone": "calm", "imageUrl": "https://example.com/new.png",
    }, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["title"] == "Edited title"
    assert r.json()["tone"] == "calm"
    assert r.json()["imageUrl"] == "https://example.com/new.png"


def test_gallery_upload_returns_media_path(client, auth_headers):
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    r = client.post("/api/v1/admin/gallery/upload",
                    files={"file": ("shot.png", png, "image/png")}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["imageUrl"].startswith("/media/gallery/")
    assert r.json()["imageUrl"].endswith(".png")


def test_gallery_upload_rejects_bad_extension(client, auth_headers):
    r = client.post("/api/v1/admin/gallery/upload",
                    files={"file": ("evil.exe", b"MZ", "application/octet-stream")}, headers=auth_headers)
    assert r.status_code == 400


def test_gallery_upload_requires_auth(client):
    r = client.post("/api/v1/admin/gallery/upload",
                    files={"file": ("x.png", b"x", "image/png")})
    assert r.status_code in (401, 403)


def test_public_gallery_is_db_driven_and_approved_only(client, auth_headers):
    # Create an approved item -> shows publicly (realtime, not static seed).
    created = client.post("/api/v1/admin/gallery", json={
        "title": "Public visible", "sportSlug": "badminton", "tone": "focused",
        "imageUrl": "https://example.com/pub.jpg", "approved": True,
    }, headers=auth_headers).json()
    pub = client.get("/api/v1/gallery").json()
    assert any(g["id"] == created["id"] for g in pub)
    assert any(g["title"] == "Public visible" for g in pub)
    # Reject it -> disappears from public.
    client.patch(f"/api/v1/admin/gallery/{created['id']}", json={"approved": False}, headers=auth_headers)
    pub2 = client.get("/api/v1/gallery").json()
    assert all(g["id"] != created["id"] for g in pub2)


def test_public_gallery_exposes_image_url(client):
    pub = client.get("/api/v1/gallery").json()
    assert pub  # seeded items present
    for g in pub:
        assert "imageUrl" in g
