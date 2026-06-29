"""Admin CMS: list all entries, update value by key."""


def test_cms_list_seeded(client, auth_headers):
    r = client.get("/api/v1/admin/cms", headers=auth_headers)
    assert r.status_code == 200
    entries = r.json()
    assert len(entries) > 0


def test_cms_entries_have_required_fields(client, auth_headers):
    entries = client.get("/api/v1/admin/cms", headers=auth_headers).json()
    for e in entries:
        assert "key" in e
        assert "label" in e
        assert "value" in e


def test_cms_update_entry(client, auth_headers):
    new_val = "Updated tagline for test."
    r = client.put("/api/v1/admin/cms/hero_tagline", json={"value": new_val}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["value"] == new_val


def test_cms_update_persists(client, auth_headers):
    new_val = "Persistent update."
    client.put("/api/v1/admin/cms/footer_tagline", json={"value": new_val}, headers=auth_headers)
    entries = client.get("/api/v1/admin/cms", headers=auth_headers).json()
    footer = next((e for e in entries if e["key"] == "footer_tagline"), None)
    assert footer is not None
    assert footer["value"] == new_val


def test_cms_update_nonexistent_key(client, auth_headers):
    r = client.put("/api/v1/admin/cms/no_such_key", json={"value": "x"}, headers=auth_headers)
    assert r.status_code == 404


def test_cms_requires_auth(client):
    r = client.get("/api/v1/admin/cms")
    assert r.status_code in (401, 403)
