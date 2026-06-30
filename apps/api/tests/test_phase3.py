"""Phase 3 — customers + status state machine."""
from datetime import date, timedelta


def _offset(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _get_available_slot(client, sport="cricket"):
    slots = client.get(f"/api/v1/slots?sport={sport}&date={_offset(1)}").json()
    return next((s for s in slots if s["available"]), None)


def _book(client, slot, name="Test User", contact="9876543210", players=2):
    return client.post("/api/v1/bookings", json={
        "name": name,
        "contact": contact,
        "slotId": slot["id"],
        "sportSlug": slot["sportSlug"],
        "date": slot["date"],
        "startTime": slot["startTime"],
        "players": players,
    })


# ── Customer upsert ────────────────────────────────────────────────────────────

def test_booking_creates_customer(client, auth_headers):
    slot = _get_available_slot(client)
    _book(client, slot, name="Alice", contact="9000000001")
    customers = client.get("/api/v1/admin/customers", headers=auth_headers).json()
    assert len(customers) == 1
    assert customers[0]["name"] == "Alice"
    assert customers[0]["phone"] == "9000000001"


def test_same_contact_reuses_customer(client, auth_headers):
    """Two bookings with the same contact → one customer row."""
    s1 = _get_available_slot(client, sport="cricket")
    s2 = _get_available_slot(client, sport="badminton")
    _book(client, s1, name="Bob", contact="9000000002")
    _book(client, s2, name="Bob Updated", contact="9000000002")
    customers = client.get("/api/v1/admin/customers", headers=auth_headers).json()
    assert len(customers) == 1
    assert customers[0]["name"] == "Bob Updated"  # name refreshed on second booking


def test_different_contacts_create_separate_customers(client, auth_headers):
    s1 = _get_available_slot(client, sport="cricket")
    s2 = _get_available_slot(client, sport="badminton")
    _book(client, s1, name="Carol", contact="9000000003")
    _book(client, s2, name="Dave",  contact="9000000004")
    customers = client.get("/api/v1/admin/customers", headers=auth_headers).json()
    assert len(customers) == 2


def test_booking_record_has_customer_id(client, auth_headers):
    slot = _get_available_slot(client)
    _book(client, slot, contact="9000000005")
    bookings = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    customers = client.get("/api/v1/admin/customers", headers=auth_headers).json()
    assert bookings[0]["customer_id"] == customers[0]["id"]


def test_customers_requires_auth(client):
    r = client.get("/api/v1/admin/customers")
    assert r.status_code in (401, 403)


# ── Status state machine ───────────────────────────────────────────────────────

def _book_and_get_id(client, auth_headers, sport="cricket"):
    slot = _get_available_slot(client, sport=sport)
    _book(client, slot)
    return client.get("/api/v1/admin/bookings", headers=auth_headers).json()[0]["id"]


def _patch(client, auth_headers, bid, status):
    return client.patch(f"/api/v1/admin/bookings/{bid}", json={"status": status}, headers=auth_headers)


def test_pending_to_confirmed(client, auth_headers):
    bid = _book_and_get_id(client, auth_headers)
    r = _patch(client, auth_headers, bid, "confirmed")
    assert r.status_code == 200
    assert r.json()["status"] == "confirmed"


def test_pending_to_cancelled(client, auth_headers):
    bid = _book_and_get_id(client, auth_headers)
    r = _patch(client, auth_headers, bid, "cancelled")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_confirmed_to_completed(client, auth_headers):
    bid = _book_and_get_id(client, auth_headers)
    _patch(client, auth_headers, bid, "confirmed")
    r = _patch(client, auth_headers, bid, "completed")
    assert r.status_code == 200
    assert r.json()["status"] == "completed"


def test_confirmed_to_no_show(client, auth_headers):
    bid = _book_and_get_id(client, auth_headers)
    _patch(client, auth_headers, bid, "confirmed")
    r = _patch(client, auth_headers, bid, "no_show")
    assert r.status_code == 200
    assert r.json()["status"] == "no_show"


def test_confirmed_to_cancelled(client, auth_headers):
    bid = _book_and_get_id(client, auth_headers)
    _patch(client, auth_headers, bid, "confirmed")
    r = _patch(client, auth_headers, bid, "cancelled")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_pending_to_completed_rejected(client, auth_headers):
    """pending → completed is not a valid transition (must confirm first)."""
    bid = _book_and_get_id(client, auth_headers)
    r = _patch(client, auth_headers, bid, "completed")
    assert r.status_code == 409


def test_pending_to_no_show_rejected(client, auth_headers):
    bid = _book_and_get_id(client, auth_headers)
    r = _patch(client, auth_headers, bid, "no_show")
    assert r.status_code == 409


def test_cancelled_is_terminal(client, auth_headers):
    """No transitions out of cancelled."""
    bid = _book_and_get_id(client, auth_headers)
    _patch(client, auth_headers, bid, "cancelled")
    r = _patch(client, auth_headers, bid, "confirmed")
    assert r.status_code == 409


def test_completed_is_terminal(client, auth_headers):
    bid = _book_and_get_id(client, auth_headers)
    _patch(client, auth_headers, bid, "confirmed")
    _patch(client, auth_headers, bid, "completed")
    r = _patch(client, auth_headers, bid, "cancelled")
    assert r.status_code == 409


def test_no_show_is_terminal(client, auth_headers):
    bid = _book_and_get_id(client, auth_headers)
    _patch(client, auth_headers, bid, "confirmed")
    _patch(client, auth_headers, bid, "no_show")
    r = _patch(client, auth_headers, bid, "completed")
    assert r.status_code == 409


def test_invalid_status_string_still_422(client, auth_headers):
    """Schema-level reject (pattern mismatch) still returns 422, not 409."""
    bid = _book_and_get_id(client, auth_headers)
    r = _patch(client, auth_headers, bid, "deleted")
    assert r.status_code == 422


def test_no_show_frees_slot(client, auth_headers):
    """no_show status is excluded from capacity, so slot becomes available again."""
    slot = _get_available_slot(client)
    _book(client, slot)
    bid = client.get("/api/v1/admin/bookings", headers=auth_headers).json()[0]["id"]
    _patch(client, auth_headers, bid, "confirmed")
    _patch(client, auth_headers, bid, "no_show")
    slots = client.get(f"/api/v1/slots?sport={slot['sportSlug']}&date={_offset(1)}").json()
    found = next((s for s in slots if s["id"] == slot["id"]), None)
    assert found is not None
    assert found["available"] is True


# ── Delete booking (admin, used by E2E cleanup) ──────────────────────────────────

def test_delete_booking_removes_it(client, auth_headers):
    bid = _book_and_get_id(client, auth_headers)
    r = client.delete(f"/api/v1/admin/bookings/{bid}", headers=auth_headers)
    assert r.status_code == 204
    remaining = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    assert all(b["id"] != bid for b in remaining)


def test_delete_booking_frees_slot(client, auth_headers):
    """Deleting a booking releases its slot capacity."""
    slot = _get_available_slot(client)
    _book(client, slot)
    bid = client.get("/api/v1/admin/bookings", headers=auth_headers).json()[0]["id"]
    client.delete(f"/api/v1/admin/bookings/{bid}", headers=auth_headers)
    slots = client.get(f"/api/v1/slots?sport={slot['sportSlug']}&date={_offset(1)}").json()
    found = next((s for s in slots if s["id"] == slot["id"]), None)
    assert found is not None
    assert found["available"] is True


def test_delete_missing_booking_404(client, auth_headers):
    r = client.delete("/api/v1/admin/bookings/does-not-exist", headers=auth_headers)
    assert r.status_code == 404


def test_delete_booking_requires_auth(client):
    r = client.delete("/api/v1/admin/bookings/whatever")
    assert r.status_code in (401, 403)
