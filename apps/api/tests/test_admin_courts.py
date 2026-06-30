"""Admin courts CRUD — create / update / deactivate / reactivate."""
from datetime import date, timedelta


def _offset(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


# ── List ──────────────────────────────────────────────────────────────────────

def test_list_courts_returns_seeded(client, auth_headers):
    courts = client.get("/api/v1/admin/courts", headers=auth_headers).json()
    assert len(courts) == 3
    sports = sorted(c["sport"] for c in courts)
    assert sports == ["badminton", "cricket", "pickleball"]


def test_list_courts_shape(client, auth_headers):
    courts = client.get("/api/v1/admin/courts", headers=auth_headers).json()
    for c in courts:
        for field in ("id", "venue_id", "sport", "name", "capacity", "active"):
            assert field in c, f"Missing field: {field}"
        assert isinstance(c["active"], bool)
        assert isinstance(c["capacity"], int) and c["capacity"] >= 1


def test_list_courts_requires_auth(client):
    r = client.get("/api/v1/admin/courts")
    assert r.status_code in (401, 403)


# ── Create ────────────────────────────────────────────────────────────────────

def test_create_court_success(client, auth_headers):
    r = client.post("/api/v1/admin/courts", json={
        "venue_id": "venue-dazy",
        "sport": "badminton",
        "name": "Court 2",
        "capacity": 2,
    }, headers=auth_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["sport"] == "badminton"
    assert body["name"] == "Court 2"
    assert body["capacity"] == 2
    assert body["active"] is True
    assert "id" in body


def test_create_court_appears_in_list(client, auth_headers):
    client.post("/api/v1/admin/courts", json={
        "venue_id": "venue-dazy", "sport": "cricket", "name": "Court 2", "capacity": 1,
    }, headers=auth_headers)
    courts = client.get("/api/v1/admin/courts", headers=auth_headers).json()
    cricket_courts = [c for c in courts if c["sport"] == "cricket"]
    assert len(cricket_courts) == 2
    names = sorted(c["name"] for c in cricket_courts)
    assert names == ["Court 1", "Court 2"]


def test_create_court_generates_slots(client, auth_headers):
    """New court with schedule rules generates its own slots."""
    r = client.post("/api/v1/admin/courts", json={
        "venue_id": "venue-dazy", "sport": "pickleball", "name": "Court 2", "capacity": 1,
    }, headers=auth_headers)
    court_id = r.json()["id"]
    day = _offset(1)
    wd = date.fromisoformat(day).weekday()
    # Give it a schedule rule
    client.post("/api/v1/admin/schedule/rules", json={
        "court_id": court_id, "weekday": wd,
        "open_time": "08:00", "close_time": "10:00", "slot_minutes": 60,
    }, headers=auth_headers)
    slots = client.get(f"/api/v1/slots?sport=pickleball&date={day}").json()
    court_slots = [s for s in slots if s["courtId"] == court_id]
    assert len(court_slots) == 2  # 08:00-10:00 = 2 slots


def test_create_court_invalid_sport(client, auth_headers):
    r = client.post("/api/v1/admin/courts", json={
        "venue_id": "venue-dazy", "sport": "hockey", "name": "Ice Rink", "capacity": 1,
    }, headers=auth_headers)
    assert r.status_code == 422


def test_create_court_missing_name(client, auth_headers):
    r = client.post("/api/v1/admin/courts", json={
        "venue_id": "venue-dazy", "sport": "cricket", "capacity": 1,
    }, headers=auth_headers)
    assert r.status_code == 422


def test_create_court_capacity_zero_rejected(client, auth_headers):
    r = client.post("/api/v1/admin/courts", json={
        "venue_id": "venue-dazy", "sport": "cricket", "name": "Zero Cap", "capacity": 0,
    }, headers=auth_headers)
    assert r.status_code == 422


def test_create_court_requires_auth(client):
    r = client.post("/api/v1/admin/courts", json={
        "venue_id": "venue-dazy", "sport": "cricket", "name": "Court X", "capacity": 1,
    })
    assert r.status_code in (401, 403)


# ── Update ────────────────────────────────────────────────────────────────────

def test_update_court_name(client, auth_headers):
    court_id = "court-cricket"
    r = client.patch(f"/api/v1/admin/courts/{court_id}",
                     json={"name": "Main Cricket Court"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Main Cricket Court"


def test_update_court_capacity(client, auth_headers):
    court_id = "court-badminton"
    r = client.patch(f"/api/v1/admin/courts/{court_id}",
                     json={"capacity": 3}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["capacity"] == 3


def test_update_court_partial(client, auth_headers):
    """Only provided fields change; others stay."""
    court_id = "court-pickleball"
    # First update name
    client.patch(f"/api/v1/admin/courts/{court_id}", json={"name": "Named"}, headers=auth_headers)
    # Then update capacity only — name must persist
    r = client.patch(f"/api/v1/admin/courts/{court_id}", json={"capacity": 4}, headers=auth_headers)
    assert r.json()["name"] == "Named"
    assert r.json()["capacity"] == 4


def test_update_court_not_found(client, auth_headers):
    r = client.patch("/api/v1/admin/courts/fake-id", json={"name": "X"}, headers=auth_headers)
    assert r.status_code == 404


def test_update_court_requires_auth(client):
    r = client.patch("/api/v1/admin/courts/court-cricket", json={"name": "X"})
    assert r.status_code in (401, 403)


# ── Deactivate (soft delete) ──────────────────────────────────────────────────

def test_deactivate_court_removes_from_active_list(client, auth_headers):
    client.delete("/api/v1/admin/courts/court-cricket", headers=auth_headers)
    courts = client.get("/api/v1/admin/courts", headers=auth_headers).json()
    active = [c for c in courts if c["active"]]
    assert not any(c["id"] == "court-cricket" for c in active)


def test_deactivate_court_still_in_full_list(client, auth_headers):
    """Deactivated court returned when listing all (active_only=False)."""
    client.delete("/api/v1/admin/courts/court-cricket", headers=auth_headers)
    courts = client.get("/api/v1/admin/courts", headers=auth_headers).json()
    found = next((c for c in courts if c["id"] == "court-cricket"), None)
    assert found is not None
    assert found["active"] is False


def test_deactivated_court_generates_no_slots(client, auth_headers):
    client.delete("/api/v1/admin/courts/court-cricket", headers=auth_headers)
    slots = client.get(f"/api/v1/slots?sport=cricket&date={_offset(1)}").json()
    assert slots == []


def test_reactivate_deactivated_court(client, auth_headers):
    client.delete("/api/v1/admin/courts/court-cricket", headers=auth_headers)
    r = client.patch("/api/v1/admin/courts/court-cricket", json={"active": True}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["active"] is True
    slots = client.get(f"/api/v1/slots?sport=cricket&date={_offset(1)}").json()
    assert len(slots) == 12  # back to full schedule


def test_deactivate_court_not_found(client, auth_headers):
    r = client.delete("/api/v1/admin/courts/nonexistent-id", headers=auth_headers)
    assert r.status_code == 404


def test_deactivate_court_requires_auth(client):
    r = client.delete("/api/v1/admin/courts/court-cricket")
    assert r.status_code in (401, 403)


# ── Slot id format ────────────────────────────────────────────────────────────

def test_slot_id_includes_court_id(client):
    """Slot IDs are court-specific: slot-{court_id}-{date}-{HHMM}."""
    day = _offset(1)
    slots = client.get(f"/api/v1/slots?sport=cricket&date={day}").json()
    assert slots
    expected_prefix = f"slot-court-cricket-{day}-"
    assert all(s["id"].startswith(expected_prefix) for s in slots)


def test_two_courts_same_sport_unique_slot_ids(client, auth_headers):
    """Two active courts for same sport produce non-overlapping slot IDs."""
    r = client.post("/api/v1/admin/courts", json={
        "venue_id": "venue-dazy", "sport": "cricket", "name": "Court 2", "capacity": 1,
    }, headers=auth_headers)
    c2_id = r.json()["id"]
    day = _offset(1)
    wd = date.fromisoformat(day).weekday()
    client.post("/api/v1/admin/schedule/rules", json={
        "court_id": c2_id, "weekday": wd,
        "open_time": "06:00", "close_time": "07:00", "slot_minutes": 60,
    }, headers=auth_headers)
    slots = client.get(f"/api/v1/slots?sport=cricket&date={day}").json()
    ids = [s["id"] for s in slots]
    assert len(ids) == len(set(ids)), "Duplicate slot IDs with two courts"


def test_slot_carries_court_name(client):
    """Each slot exposes courtName matching the seeded court name."""
    day = _offset(1)
    slots = client.get(f"/api/v1/slots?sport=badminton&date={day}").json()
    assert slots
    assert all(s["courtName"] == "Court 1" for s in slots)
