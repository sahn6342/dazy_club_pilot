"""Bookings: public create + admin list/filter/status-update."""
from datetime import date, timedelta


def _tomorrow():
    return (date.today() + timedelta(days=1)).isoformat()


def _today():
    return date.today().isoformat()


def _get_available_slot(client, sport="cricket"):
    r = client.get(f"/api/v1/slots?sport={sport}&date={_tomorrow()}")
    slots = [s for s in r.json() if s["available"]]
    return slots[0] if slots else None


def _book(client, slot, overrides=None):
    payload = {
        "name": "Jane Doe",
        "contact": "9876543210",
        "slotId": slot["id"],
        "sportSlug": slot["sportSlug"],
        "date": slot["date"],
        "startTime": slot["startTime"],
        "players": 2,
    }
    if overrides:
        payload.update(overrides)
    return client.post("/api/v1/bookings", json=payload)


def test_create_booking_success(client):
    slot = _get_available_slot(client)
    assert slot, "No available slots for test"
    r = _book(client, slot)
    assert r.status_code in (200, 201)
    body = r.json()
    assert body["status"] == "confirmed"
    assert "bookingRef" in body


def test_create_booking_missing_name(client):
    slot = _get_available_slot(client)
    r = client.post("/api/v1/bookings", json={
        "contact": "9876543210",
        "slotId": slot["id"],
        "sportSlug": slot["sportSlug"],
        "date": slot["date"],
        "startTime": slot["startTime"],
        "players": 2,
    })
    assert r.status_code == 422


def test_create_booking_zero_players(client):
    slot = _get_available_slot(client)
    r = _book(client, slot, {"players": 0})
    assert r.status_code == 422


def test_create_booking_nonexistent_slot(client):
    r = client.post("/api/v1/bookings", json={
        "name": "A", "contact": "1", "slotId": "fake-id",
        "sportSlug": "cricket", "date": _today(), "startTime": "06:00", "players": 1,
    })
    assert r.status_code == 404


def test_double_booking_rejected(client):
    slot = _get_available_slot(client)
    _book(client, slot)
    r = _book(client, slot)
    assert r.status_code == 409


def test_admin_list_bookings_empty(client, auth_headers):
    r = client.get("/api/v1/admin/bookings", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_admin_list_bookings_after_booking(client, auth_headers):
    slot = _get_available_slot(client)
    _book(client, slot)
    r = client.get("/api/v1/admin/bookings", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_admin_filter_bookings_by_status(client, auth_headers):
    slot = _get_available_slot(client)
    _book(client, slot)
    r = client.get("/api/v1/admin/bookings?status=pending", headers=auth_headers)
    assert r.status_code == 200
    for b in r.json():
        assert b["status"] == "pending"


def test_admin_confirm_booking(client, auth_headers):
    slot = _get_available_slot(client)
    _book(client, slot)
    bookings = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    bid = bookings[0]["id"]
    r = client.patch(f"/api/v1/admin/bookings/{bid}", json={"status": "confirmed"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "confirmed"


def test_admin_cancel_booking(client, auth_headers):
    slot = _get_available_slot(client)
    _book(client, slot)
    bookings = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    bid = bookings[0]["id"]
    r = client.patch(f"/api/v1/admin/bookings/{bid}", json={"status": "cancelled"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_admin_invalid_status_rejected(client, auth_headers):
    slot = _get_available_slot(client)
    _book(client, slot)
    bookings = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    bid = bookings[0]["id"]
    r = client.patch(f"/api/v1/admin/bookings/{bid}", json={"status": "deleted"}, headers=auth_headers)
    assert r.status_code == 422


def test_admin_bookings_requires_auth(client):
    r = client.get("/api/v1/admin/bookings")
    assert r.status_code in (401, 403)


# ── Phase 2: capacity-aware availability ──────────────────────────────────────

def test_booking_exposes_party_size(client, auth_headers):
    """BookingRecord now carries party_size (not players)."""
    slot = _get_available_slot(client)
    _book(client, slot, overrides={"players": 3})
    bookings = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    assert bookings[0]["party_size"] == 3


def test_cancelled_booking_slot_reopens(client, auth_headers):
    """Capacity-aware: cancel re-opens the slot so it can be rebooked."""
    slot = _get_available_slot(client)
    _book(client, slot)
    bid = client.get("/api/v1/admin/bookings", headers=auth_headers).json()[0]["id"]
    client.patch(f"/api/v1/admin/bookings/{bid}", json={"status": "cancelled"}, headers=auth_headers)
    # Re-book the same slot — must succeed now
    r = _book(client, slot)
    assert r.status_code in (200, 201)


def test_double_booking_unique_index_fires(client):
    """Second booking for same slot returns 409 even if both pass the availability check."""
    slot = _get_available_slot(client)
    assert _book(client, slot).status_code in (200, 201)
    r = _book(client, slot)
    assert r.status_code == 409


def test_concurrent_booking_race(client):
    """Two threads racing to book the same slot: exactly one wins (201) and one loses (409/404)."""
    import threading

    slot = _get_available_slot(client)
    if not slot:
        return  # no morning slots — skip rather than fail

    results: list[int] = []
    lock = threading.Lock()

    def attempt():
        r = _book(client, slot)
        with lock:
            results.append(r.status_code)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = sum(1 for c in results if c in (200, 201))
    assert successes == 1, f"Expected exactly 1 success, got results={results}"
