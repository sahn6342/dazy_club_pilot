"""Phase 1 — schedule as data: admin CRUD + exception-driven availability."""
from datetime import date, timedelta


def _offset(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def test_admin_list_courts(client, auth_headers):
    courts = client.get("/api/v1/admin/courts", headers=auth_headers).json()
    sports = sorted(c["sport"] for c in courts)
    assert sports == ["badminton", "cricket", "pickleball"]
    assert all(c["capacity"] == 1 for c in courts)


def test_seeded_rules_present(client, auth_headers):
    rules = client.get("/api/v1/admin/schedule/rules?court_id=court-cricket", headers=auth_headers).json()
    # 3 blocks per weekday * 7 weekdays
    assert len(rules) == 21


def test_closed_exception_zero_slots(client, auth_headers):
    day = _offset(2)
    r = client.post("/api/v1/admin/schedule/exceptions",
                    json={"court_id": "court-cricket", "day": day, "closed": True},
                    headers=auth_headers)
    assert r.status_code == 201
    slots = client.get(f"/api/v1/slots?sport=cricket&date={day}").json()
    assert slots == []


def test_special_hours_exception_clips(client, auth_headers):
    day = _offset(3)
    r = client.post("/api/v1/admin/schedule/exceptions",
                    json={"court_id": "court-cricket", "day": day, "closed": False,
                          "open_time": "09:00", "close_time": "11:00"},
                    headers=auth_headers)
    assert r.status_code == 201
    slots = client.get(f"/api/v1/slots?sport=cricket&date={day}").json()
    times = sorted(s["startTime"] for s in slots)
    assert times == ["09:00", "10:00"]


def test_exception_only_affects_its_court(client, auth_headers):
    day = _offset(2)
    client.post("/api/v1/admin/schedule/exceptions",
                json={"court_id": "court-cricket", "day": day, "closed": True},
                headers=auth_headers)
    # badminton unaffected
    badminton = client.get(f"/api/v1/slots?sport=badminton&date={day}").json()
    assert len(badminton) == 12


def test_create_rule_and_delete(client, auth_headers):
    r = client.post("/api/v1/admin/schedule/rules",
                    json={"court_id": "court-badminton", "weekday": 0,
                          "open_time": "21:00", "close_time": "22:00", "slot_minutes": 60},
                    headers=auth_headers)
    assert r.status_code == 201
    rule_id = r.json()["id"]
    d = client.delete(f"/api/v1/admin/schedule/rules/{rule_id}", headers=auth_headers)
    assert d.status_code == 204


def test_rule_for_unknown_court_rejected(client, auth_headers):
    r = client.post("/api/v1/admin/schedule/rules",
                    json={"court_id": "court-nope", "weekday": 0,
                          "open_time": "09:00", "close_time": "10:00"},
                    headers=auth_headers)
    assert r.status_code == 404


def test_schedule_requires_auth(client):
    assert client.get("/api/v1/admin/schedule/rules").status_code in (401, 403)
    assert client.get("/api/v1/admin/courts").status_code in (401, 403)


# ── Phase 5: venue-wide (all-courts) exceptions ───────────────────────────────

def test_venue_wide_exception_closes_all_courts(client, auth_headers):
    """court_id=null exception closes EVERY sport that day."""
    day = _offset(4)
    r = client.post("/api/v1/admin/schedule/exceptions",
                    json={"court_id": None, "day": day, "closed": True},
                    headers=auth_headers)
    assert r.status_code == 201
    assert r.json()["court_id"] is None
    for sport in ("cricket", "badminton", "pickleball"):
        slots = client.get(f"/api/v1/slots?sport={sport}&date={day}").json()
        assert slots == [], f"{sport} should be closed on {day}"


def test_venue_wide_exception_listed_on_every_court(client, auth_headers):
    """A venue-wide exception appears when listing any court's exceptions."""
    day = _offset(5)
    client.post("/api/v1/admin/schedule/exceptions",
                json={"court_id": None, "day": day, "closed": True}, headers=auth_headers)
    for cid in ("court-cricket", "court-badminton"):
        rows = client.get(f"/api/v1/admin/schedule/exceptions?court_id={cid}", headers=auth_headers).json()
        assert any(x["day"] == day and x["court_id"] is None for x in rows)


def test_court_specific_exception_still_scoped(client, auth_headers):
    """A court-specific exception does not close other courts."""
    day = _offset(6)
    client.post("/api/v1/admin/schedule/exceptions",
                json={"court_id": "court-cricket", "day": day, "closed": True}, headers=auth_headers)
    assert client.get(f"/api/v1/slots?sport=cricket&date={day}").json() == []
    assert len(client.get(f"/api/v1/slots?sport=badminton&date={day}").json()) == 12


def test_court_specific_exception_wins_over_venue_wide(client, auth_headers):
    """When both exist for a day, the court-specific one takes precedence."""
    day = _offset(4)
    # venue-wide: closed; cricket-specific: special hours 09:00-11:00
    client.post("/api/v1/admin/schedule/exceptions",
                json={"court_id": None, "day": day, "closed": True}, headers=auth_headers)
    client.post("/api/v1/admin/schedule/exceptions",
                json={"court_id": "court-cricket", "day": day, "closed": False,
                      "open_time": "09:00", "close_time": "11:00"}, headers=auth_headers)
    cricket = sorted(s["startTime"] for s in client.get(f"/api/v1/slots?sport=cricket&date={day}").json())
    assert cricket == ["09:00", "10:00"]  # court-specific special hours win
    # badminton still closed by the venue-wide rule
    assert client.get(f"/api/v1/slots?sport=badminton&date={day}").json() == []
