"""Slots: availability grid for each sport/date combination."""
from datetime import date, timedelta


def _today():
    return date.today().isoformat()


def _tomorrow():
    return (date.today() + timedelta(days=1)).isoformat()


def test_slots_returns_list(client):
    r = client.get(f"/api/v1/slots?sport=cricket&date={_today()}")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_slots_filter_by_sport(client):
    r = client.get(f"/api/v1/slots?sport=badminton&date={_today()}")
    assert r.status_code == 200
    for slot in r.json():
        assert slot["sportSlug"] == "badminton"


def test_slots_filter_by_date(client):
    r = client.get(f"/api/v1/slots?sport=cricket&date={_tomorrow()}")
    assert r.status_code == 200
    for slot in r.json():
        assert slot["date"] == _tomorrow()


def test_slots_have_required_fields(client):
    r = client.get(f"/api/v1/slots?sport=pickleball&date={_tomorrow()}")
    assert r.status_code == 200
    slots = r.json()
    assert len(slots) > 0
    s = slots[0]
    for field in ("id", "sportSlug", "date", "startTime", "endTime", "available", "maxPlayers"):
        assert field in s, f"Missing field: {field}"


def test_slots_unknown_sport_returns_empty(client):
    r = client.get(f"/api/v1/slots?sport=hockey&date={_today()}")
    assert r.status_code == 200
    assert r.json() == []


def test_booking_marks_slot_unavailable(client):
    r = client.get(f"/api/v1/slots?sport=cricket&date={_tomorrow()}")
    available = [s for s in r.json() if s["available"]]
    assert len(available) > 0
    slot = available[0]

    client.post("/api/v1/bookings", json={
        "name": "Test User",
        "contact": "9999999999",
        "slotId": slot["id"],
        "sportSlug": "cricket",
        "date": slot["date"],
        "startTime": slot["startTime"],
        "players": 2,
    })

    r2 = client.get(f"/api/v1/slots?sport=cricket&date={_tomorrow()}")
    updated = next((s for s in r2.json() if s["id"] == slot["id"]), None)
    assert updated is not None
    assert updated["available"] is False
