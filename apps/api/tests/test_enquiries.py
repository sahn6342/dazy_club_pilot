"""Enquiries: contact + corporate submission and admin management."""


_CONTACT = {
    "name": "Riya Sharma",
    "contact": "9800000001",
    "interestedSport": "cricket",
    "message": "Interested in weekend sessions.",
}

_CORPORATE = {
    "contactName": "Arjun Mehta",
    "company": "Acme Corp",
    "contact": "9800000002",
    "estimatedGroupSize": 15,
    "eventType": "team outing",
    "preferredDate": "2026-08-10",
    "preferredSport": "badminton",
}


def test_contact_enquiry_success(client):
    r = client.post("/api/v1/contact-enquiries", json=_CONTACT)
    assert r.status_code in (200, 201)
    assert r.json()["status"] == "received"


def test_contact_enquiry_missing_name(client):
    r = client.post("/api/v1/contact-enquiries", json={"contact": "9800000001"})
    assert r.status_code == 422


def test_contact_enquiry_empty_name(client):
    r = client.post("/api/v1/contact-enquiries", json={"name": "", "contact": "9800000001"})
    assert r.status_code == 422


def test_corporate_enquiry_success(client):
    r = client.post("/api/v1/corporate-enquiries", json=_CORPORATE)
    assert r.status_code in (200, 201)
    assert r.json()["status"] == "received"


def test_corporate_enquiry_zero_group_size(client):
    bad = {**_CORPORATE, "estimatedGroupSize": 0}
    r = client.post("/api/v1/corporate-enquiries", json=bad)
    assert r.status_code == 422


def test_corporate_enquiry_missing_company(client):
    bad = {k: v for k, v in _CORPORATE.items() if k != "company"}
    r = client.post("/api/v1/corporate-enquiries", json=bad)
    assert r.status_code == 422


def test_admin_list_enquiries_empty(client, auth_headers):
    r = client.get("/api/v1/admin/enquiries", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_admin_list_enquiries_after_submission(client, auth_headers):
    client.post("/api/v1/contact-enquiries", json=_CONTACT)
    client.post("/api/v1/corporate-enquiries", json=_CORPORATE)
    r = client.get("/api/v1/admin/enquiries", headers=auth_headers)
    assert len(r.json()) == 2


def test_admin_filter_enquiries_by_type(client, auth_headers):
    client.post("/api/v1/contact-enquiries", json=_CONTACT)
    client.post("/api/v1/corporate-enquiries", json=_CORPORATE)
    r = client.get("/api/v1/admin/enquiries?type=contact", headers=auth_headers)
    assert all(e["type"] == "contact" for e in r.json())


def test_admin_mark_enquiry_handled(client, auth_headers):
    client.post("/api/v1/contact-enquiries", json=_CONTACT)
    enquiries = client.get("/api/v1/admin/enquiries", headers=auth_headers).json()
    eid = enquiries[0]["id"]
    r = client.patch(f"/api/v1/admin/enquiries/{eid}", json={"status": "handled"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "handled"


def test_admin_enquiries_requires_auth(client):
    r = client.get("/api/v1/admin/enquiries")
    assert r.status_code in (401, 403)
