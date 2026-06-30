"""Admin CMS: create / edit (value+label) / delete (Phase 5)."""


def test_create_cms_entry_appears(client, auth_headers):
    r = client.post("/api/v1/admin/cms",
                    json={"key": "faq_parking", "label": "FAQ: Parking", "value": "Free on-site parking."},
                    headers=auth_headers)
    assert r.status_code == 201
    rows = client.get("/api/v1/admin/cms", headers=auth_headers).json()
    assert any(e["key"] == "faq_parking" and e["label"] == "FAQ: Parking" for e in rows)


def test_create_duplicate_key_409(client, auth_headers):
    # hero_tagline is seeded.
    r = client.post("/api/v1/admin/cms",
                    json={"key": "hero_tagline", "label": "Dup", "value": "x"}, headers=auth_headers)
    assert r.status_code == 409


def test_create_invalid_key_422(client, auth_headers):
    r = client.post("/api/v1/admin/cms",
                    json={"key": "Bad Key!", "label": "L", "value": "v"}, headers=auth_headers)
    assert r.status_code == 422


def test_put_updates_value_and_label(client, auth_headers):
    r = client.put("/api/v1/admin/cms/faq_sports",
                   json={"value": "Cricket and Pickleball.", "label": "FAQ: Our sports"},
                   headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["value"] == "Cricket and Pickleball."
    assert r.json()["label"] == "FAQ: Our sports"


def test_put_value_only_still_works(client, auth_headers):
    r = client.put("/api/v1/admin/cms/footer_tagline",
                   json={"value": "New footer."}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["value"] == "New footer."


def test_put_nonexistent_404(client, auth_headers):
    r = client.put("/api/v1/admin/cms/nope_key", json={"value": "x"}, headers=auth_headers)
    assert r.status_code == 404


def test_delete_removes(client, auth_headers):
    client.post("/api/v1/admin/cms",
                json={"key": "temp_key", "label": "Temp", "value": "v"}, headers=auth_headers)
    assert client.delete("/api/v1/admin/cms/temp_key", headers=auth_headers).status_code == 204
    rows = client.get("/api/v1/admin/cms", headers=auth_headers).json()
    assert all(e["key"] != "temp_key" for e in rows)


def test_delete_nonexistent_404(client, auth_headers):
    assert client.delete("/api/v1/admin/cms/nope_key", headers=auth_headers).status_code == 404


def test_cms_crud_requires_auth(client):
    assert client.post("/api/v1/admin/cms", json={}).status_code in (401, 403)
    assert client.delete("/api/v1/admin/cms/x").status_code in (401, 403)
