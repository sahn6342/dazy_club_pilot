"""
Comprehensive positive (happy-path) tests.
Every public and admin endpoint hit with valid data, covering field presence,
value correctness, and cross-resource consistency.
"""
import re
from datetime import date, timedelta


# ── helpers ──────────────────────────────────────────────────────────────────

def _offset(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _future() -> str:
    return _offset(1)


def _book(client, sport="cricket", day=None, players=2, name="Happy User", contact="9123456789"):
    day = day or _future()
    slots = client.get(f"/api/v1/slots?sport={sport}&date={day}").json()
    slot = next((s for s in slots if s["available"]), None)
    assert slot, f"No available slot for {sport} on {day}"
    r = client.post("/api/v1/bookings", json={
        "name": name, "contact": contact,
        "slotId": slot["id"], "sportSlug": sport,
        "date": slot["date"], "startTime": slot["startTime"],
        "players": players,
    })
    assert r.status_code in (200, 201), r.text
    return r.json(), slot


# ── Health ────────────────────────────────────────────────────────────────────

def test_health_returns_ok(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"


# ── Slots — shape & field correctness ────────────────────────────────────────

def test_slot_shape_complete(client):
    """Every slot has all required fields with correct types."""
    slots = client.get(f"/api/v1/slots?sport=cricket&date={_future()}").json()
    assert slots
    for s in slots:
        assert isinstance(s["id"], str) and s["id"].startswith("slot-")
        assert s["sportSlug"] == "cricket"
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", s["date"])
        assert re.match(r"^\d{2}:\d{2}$", s["startTime"])
        assert re.match(r"^\d{2}:\d{2}$", s["endTime"])
        assert isinstance(s["available"], bool)
        assert isinstance(s["maxPlayers"], int) and s["maxPlayers"] > 0
        assert isinstance(s["courtId"], str)
        assert isinstance(s["courtName"], str)  # court display name


def test_slot_id_format(client):
    """Slot id = slot-{court_id}-{YYYY-MM-DD}-{HHMM}."""
    day = _future()
    slots = client.get(f"/api/v1/slots?sport=badminton&date={day}").json()
    expected_prefix = f"slot-court-badminton-{day}-"
    assert all(s["id"].startswith(expected_prefix) for s in slots)


def test_slot_max_players_per_sport(client):
    """maxPlayers respects per-sport caps from _MAX_PLAYERS."""
    day = _future()
    for sport, expected_max in [("cricket", 11), ("badminton", 4), ("pickleball", 6)]:
        slots = client.get(f"/api/v1/slots?sport={sport}&date={day}").json()
        assert all(s["maxPlayers"] == expected_max for s in slots), \
            f"{sport} expected maxPlayers={expected_max}"


def test_all_slots_available_on_clean_db(client):
    """Fresh DB: every slot is available."""
    slots = client.get(f"/api/v1/slots?sport=cricket&date={_future()}").json()
    assert all(s["available"] for s in slots)


def test_slots_court_id_matches_sport(client):
    """courtId is court-{sport} as seeded."""
    for sport in ("cricket", "badminton", "pickleball"):
        slots = client.get(f"/api/v1/slots?sport={sport}&date={_future()}").json()
        assert all(s["courtId"] == f"court-{sport}" for s in slots)


def test_slots_start_before_end(client):
    """startTime < endTime for every slot."""
    slots = client.get(f"/api/v1/slots?sport=pickleball&date={_future()}").json()
    for s in slots:
        assert s["startTime"] < s["endTime"]


def test_slots_no_overlap(client):
    """No two slots for the same sport/date/court overlap."""
    slots = client.get(f"/api/v1/slots?sport=cricket&date={_future()}").json()
    times = [(s["startTime"], s["endTime"]) for s in slots]
    for i, (s1, e1) in enumerate(times):
        for s2, e2 in times[i + 1:]:
            assert e1 <= s2 or e2 <= s1, f"Overlap: {s1}-{e1} vs {s2}-{e2}"


def test_slots_independent_per_sport(client):
    """Booking cricket slot does not affect badminton or pickleball slots."""
    day = _future()
    cricket_slots = client.get(f"/api/v1/slots?sport=cricket&date={day}").json()
    slot = next(s for s in cricket_slots if s["available"])
    client.post("/api/v1/bookings", json={
        "name": "X", "contact": "9000000010",
        "slotId": slot["id"], "sportSlug": "cricket",
        "date": slot["date"], "startTime": slot["startTime"], "players": 1,
    })
    for sport in ("badminton", "pickleball"):
        others = client.get(f"/api/v1/slots?sport={sport}&date={day}").json()
        assert all(s["available"] for s in others), f"{sport} slots wrongly blocked"


# ── Bookings — positive paths ─────────────────────────────────────────────────

def test_booking_response_fields(client):
    """POST /bookings returns all expected fields. Cricket is priced, so
    Phase 3 (online prepay) reserves the slot as 'pending' pending payment,
    not 'confirmed' immediately."""
    result, slot = _book(client)
    for key in ("status", "bookingRef", "name", "sport", "date", "time", "paymentRequired"):
        assert key in result, f"Missing key: {key}"
    assert result["status"] == "pending"
    assert result["paymentRequired"] is True
    assert result["sport"] == "cricket"
    assert result["name"] == "Happy User"


def test_booking_ref_format(client):
    """bookingRef is 8-char uppercase alphanumeric."""
    result, _ = _book(client)
    ref = result["bookingRef"]
    assert len(ref) == 8
    assert ref == ref.upper()
    assert re.match(r"^[A-Z0-9]{8}$", ref)


def test_booking_with_message_stored(client, auth_headers):
    """Optional message field is stored and returned via admin API."""
    day = _future()
    slots = client.get(f"/api/v1/slots?sport=cricket&date={day}").json()
    slot = next(s for s in slots if s["available"])
    client.post("/api/v1/bookings", json={
        "name": "Msg Tester", "contact": "9111111111",
        "slotId": slot["id"], "sportSlug": "cricket",
        "date": slot["date"], "startTime": slot["startTime"],
        "players": 1, "message": "Please confirm ASAP.",
    })
    bookings = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    assert bookings[0]["message"] == "Please confirm ASAP."


def test_booking_party_size_stored(client, auth_headers):
    """party_size is persisted correctly."""
    _book(client, players=5)
    bookings = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    assert bookings[0]["party_size"] == 5


def test_booking_links_correct_customer(client, auth_headers):
    """Booking.customer_id references the created customer."""
    _book(client, name="Priya K", contact="9222222222")
    bookings = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    customers = client.get("/api/v1/admin/customers", headers=auth_headers).json()
    assert bookings[0]["customer_id"] == customers[0]["id"]
    assert customers[0]["phone"] == "9222222222"


def test_multiple_bookings_different_sports(client, auth_headers):
    """Book one slot each for cricket and badminton — both appear in admin list."""
    _book(client, sport="cricket", contact="9300000001")
    _book(client, sport="badminton", contact="9300000002")
    bookings = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    assert len(bookings) == 2
    sports = {b["sportSlug"] for b in bookings}
    assert sports == {"cricket", "badminton"}


def test_booking_filter_by_sport(client, auth_headers):
    """Admin filter by sport returns only that sport's bookings."""
    _book(client, sport="cricket", contact="9400000001")
    _book(client, sport="pickleball", contact="9400000002")
    r = client.get("/api/v1/admin/bookings?sport=cricket", headers=auth_headers)
    assert r.status_code == 200
    assert all(b["sportSlug"] == "cricket" for b in r.json())
    assert len(r.json()) == 1


def test_booking_filter_by_date(client, auth_headers):
    """Admin filter by date returns only that day's bookings."""
    day1, day2 = _offset(1), _offset(2)
    _book(client, day=day1, contact="9500000001")
    _book(client, day=day2, contact="9500000002")
    r = client.get(f"/api/v1/admin/bookings?date={day1}", headers=auth_headers)
    assert all(b["date"] == day1 for b in r.json())
    assert len(r.json()) == 1


def test_booking_filter_by_status(client, auth_headers):
    """Filter by pending returns only pending bookings."""
    _book(client, contact="9600000001")
    bookings = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    bid = bookings[0]["id"]
    client.patch(f"/api/v1/admin/bookings/{bid}", json={"status": "confirmed"}, headers=auth_headers)
    _book(client, sport="badminton", contact="9600000002")

    pending = client.get("/api/v1/admin/bookings?status=pending", headers=auth_headers).json()
    confirmed = client.get("/api/v1/admin/bookings?status=confirmed", headers=auth_headers).json()
    assert all(b["status"] == "pending" for b in pending)
    assert all(b["status"] == "confirmed" for b in confirmed)
    assert len(pending) == 1 and len(confirmed) == 1


def test_full_booking_lifecycle(client, auth_headers):
    """pending → confirmed → completed; slot freed only after terminal state."""
    day = _future()
    result, slot = _book(client, day=day)
    bookings = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    bid = bookings[0]["id"]

    # pending: slot blocked
    slots = client.get(f"/api/v1/slots?sport=cricket&date={day}").json()
    assert not next(s for s in slots if s["id"] == slot["id"])["available"]

    # → confirmed
    r = client.patch(f"/api/v1/admin/bookings/{bid}", json={"status": "confirmed"}, headers=auth_headers)
    assert r.json()["status"] == "confirmed"
    # still blocked
    slots = client.get(f"/api/v1/slots?sport=cricket&date={day}").json()
    assert not next(s for s in slots if s["id"] == slot["id"])["available"]

    # → completed
    r = client.patch(f"/api/v1/admin/bookings/{bid}", json={"status": "completed"}, headers=auth_headers)
    assert r.json()["status"] == "completed"
    # completed counts as active (party still used the slot) — slot stays blocked for that historical date
    # (completed is in active statuses for availability; no_show/cancelled free it)


def test_booking_slot_freed_on_cancel(client, auth_headers):
    """Cancel frees the slot immediately."""
    day = _future()
    _, slot = _book(client, day=day)
    bid = client.get("/api/v1/admin/bookings", headers=auth_headers).json()[0]["id"]
    client.patch(f"/api/v1/admin/bookings/{bid}", json={"status": "cancelled"}, headers=auth_headers)
    slots = client.get(f"/api/v1/slots?sport=cricket&date={day}").json()
    assert next(s for s in slots if s["id"] == slot["id"])["available"] is True


def test_booking_slot_freed_on_no_show(client, auth_headers):
    """no_show (via confirmed) frees the slot."""
    day = _future()
    _, slot = _book(client, day=day)
    bid = client.get("/api/v1/admin/bookings", headers=auth_headers).json()[0]["id"]
    client.patch(f"/api/v1/admin/bookings/{bid}", json={"status": "confirmed"}, headers=auth_headers)
    client.patch(f"/api/v1/admin/bookings/{bid}", json={"status": "no_show"}, headers=auth_headers)
    slots = client.get(f"/api/v1/slots?sport=cricket&date={day}").json()
    assert next(s for s in slots if s["id"] == slot["id"])["available"] is True


# ── Enquiries — positive paths ─────────────────────────────────────────────────

def test_contact_enquiry_all_fields_stored(client, auth_headers):
    """All optional fields submitted by user are stored."""
    client.post("/api/v1/contact-enquiries", json={
        "name": "Deepa R", "contact": "9700000001",
        "interestedSport": "pickleball",
        "message": "Looking for evening slots.",
    })
    enquiries = client.get("/api/v1/admin/enquiries", headers=auth_headers).json()
    e = enquiries[0]
    assert e["name"] == "Deepa R"
    assert e["contact"] == "9700000001"
    assert e["interestedSport"] == "pickleball"
    assert e["message"] == "Looking for evening slots."
    assert e["type"] == "contact"
    assert e["status"] == "new"


def test_corporate_enquiry_all_fields_stored(client, auth_headers):
    """All corporate fields stored and retrievable."""
    client.post("/api/v1/corporate-enquiries", json={
        "contactName": "Vikram S", "company": "Techno Corp",
        "contact": "9700000002", "estimatedGroupSize": 25,
        "eventType": "annual tournament", "preferredDate": "2026-09-15",
        "preferredSport": "cricket", "message": "Need full ground for a day.",
    })
    enquiries = client.get("/api/v1/admin/enquiries", headers=auth_headers).json()
    e = enquiries[0]
    assert e["type"] == "corporate"
    assert e["company"] == "Techno Corp"
    assert e["estimatedGroupSize"] == 25
    assert e["eventType"] == "annual tournament"
    assert e["preferredSport"] == "cricket"


def test_enquiry_status_transitions(client, auth_headers):
    """new → handled transition works."""
    client.post("/api/v1/contact-enquiries", json={"name": "X", "contact": "9700000003"})
    eid = client.get("/api/v1/admin/enquiries", headers=auth_headers).json()[0]["id"]
    r = client.patch(f"/api/v1/admin/enquiries/{eid}", json={"status": "handled"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "handled"
    # Verify persisted
    handled = client.get("/api/v1/admin/enquiries?status=handled", headers=auth_headers).json()
    assert len(handled) == 1


def test_admin_enquiry_filter_by_type_and_status(client, auth_headers):
    """Combined filter: type=corporate returns only corporate."""
    client.post("/api/v1/contact-enquiries", json={"name": "A", "contact": "9800000010"})
    client.post("/api/v1/corporate-enquiries", json={
        "contactName": "B", "company": "Corp", "contact": "9800000011", "estimatedGroupSize": 5,
    })
    r = client.get("/api/v1/admin/enquiries?type=corporate", headers=auth_headers)
    assert all(e["type"] == "corporate" for e in r.json())


# ── Customers — positive paths ────────────────────────────────────────────────

def test_customer_record_has_all_fields(client, auth_headers):
    """Customer record has id, name, phone, createdAt."""
    _book(client, name="Ananya M", contact="9900000001")
    customer = client.get("/api/v1/admin/customers", headers=auth_headers).json()[0]
    for field in ("id", "name", "phone", "createdAt"):
        assert field in customer, f"Missing field: {field}"
    assert customer["name"] == "Ananya M"
    assert customer["phone"] == "9900000001"


def test_multiple_bookings_same_customer_one_record(client, auth_headers):
    """Repeated bookings by same contact produce exactly one customer."""
    _book(client, sport="cricket",   contact="9900000002", name="Rohan P")
    _book(client, sport="badminton", contact="9900000002", name="Rohan P")
    _book(client, sport="pickleball",contact="9900000002", name="Rohan P")
    customers = client.get("/api/v1/admin/customers", headers=auth_headers).json()
    assert len(customers) == 1
    bookings = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    assert len(bookings) == 3
    assert all(b["customer_id"] == customers[0]["id"] for b in bookings)


# ── Schedule — positive paths ─────────────────────────────────────────────────

def test_custom_rule_generates_slots(client, auth_headers):
    """Add a new late-night rule; extra slot appears in the grid."""
    day = _offset(3)
    wd = date.fromisoformat(day).weekday()
    r = client.post("/api/v1/admin/schedule/rules", json={
        "court_id": "court-pickleball", "weekday": wd,
        "open_time": "22:00", "close_time": "23:00", "slot_minutes": 60,
    }, headers=auth_headers)
    assert r.status_code == 201
    rule_id = r.json()["id"]

    slots = client.get(f"/api/v1/slots?sport=pickleball&date={day}").json()
    times = [s["startTime"] for s in slots]
    assert "22:00" in times

    # Cleanup
    client.delete(f"/api/v1/admin/schedule/rules/{rule_id}", headers=auth_headers)
    slots_after = client.get(f"/api/v1/slots?sport=pickleball&date={day}").json()
    assert "22:00" not in [s["startTime"] for s in slots_after]


def test_exception_restores_after_delete(client, auth_headers):
    """Delete a closed exception → slots return for that day."""
    day = _offset(2)
    r = client.post("/api/v1/admin/schedule/exceptions", json={
        "court_id": "court-cricket", "day": day, "closed": True,
    }, headers=auth_headers)
    exc_id = r.json()["id"]
    assert client.get(f"/api/v1/slots?sport=cricket&date={day}").json() == []

    client.delete(f"/api/v1/admin/schedule/exceptions/{exc_id}", headers=auth_headers)
    assert len(client.get(f"/api/v1/slots?sport=cricket&date={day}").json()) == 12


# ── Gallery & Testimonials — public endpoint positive ─────────────────────────

def test_public_gallery_shape(client, auth_headers):
    """Public gallery returns all seed items with expected fields."""
    public = client.get("/api/v1/gallery").json()
    assert len(public) > 0
    for item in public:
        assert "id" in item
        assert "title" in item
        assert "sportSlug" in item
    admin = client.get("/api/v1/admin/gallery", headers=auth_headers).json()
    assert len(public) == len(admin)


def test_public_testimonials_shape(client, auth_headers):
    """Public testimonials returns all seed items with expected fields."""
    public = client.get("/api/v1/testimonials").json()
    assert len(public) > 0
    for item in public:
        assert "id" in item
        assert "name" in item
        assert "quote" in item
    admin = client.get("/api/v1/admin/testimonials", headers=auth_headers).json()
    assert len(public) == len(admin)


# ── CMS — positive ────────────────────────────────────────────────────────────

def test_cms_all_seed_keys_present(client, auth_headers):
    """All expected CMS keys exist after seeding."""
    entries = client.get("/api/v1/admin/cms", headers=auth_headers).json()
    keys = {e["key"] for e in entries}
    for expected in ("faq_booking", "faq_sports", "faq_corporate", "faq_group_size",
                     "hero_tagline", "hero_copy", "footer_tagline"):
        assert expected in keys, f"Missing CMS key: {expected}"


def test_cms_round_trip_update(client, auth_headers):
    """Update a key, retrieve it, verify the value round-trips exactly."""
    val = "New hero tagline — 2026 edition! 🏏"
    client.put("/api/v1/admin/cms/hero_tagline", json={"value": val}, headers=auth_headers)
    entries = client.get("/api/v1/admin/cms", headers=auth_headers).json()
    found = next(e for e in entries if e["key"] == "hero_tagline")
    assert found["value"] == val


# ── Cross-cutting: auth tokens work for all admin endpoints ───────────────────

def test_manager_token_accesses_all_non_user_endpoints(client, auth_headers):
    """Manager role can reach all admin sections except /admin/users."""
    client.post("/api/v1/admin/users", json={"username": "mgr_all", "password": "secure456"}, headers=auth_headers)
    token = client.post("/api/v1/admin/login", json={"username": "mgr_all", "password": "secure456"}).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/v1/admin/bookings", headers=h).status_code == 200
    assert client.get("/api/v1/admin/enquiries", headers=h).status_code == 200
    assert client.get("/api/v1/admin/gallery", headers=h).status_code == 200
    assert client.get("/api/v1/admin/testimonials", headers=h).status_code == 200
    assert client.get("/api/v1/admin/cms", headers=h).status_code == 200
    assert client.get("/api/v1/admin/schedule/rules", headers=h).status_code == 200
    assert client.get("/api/v1/admin/customers", headers=h).status_code == 200
    assert client.get("/api/v1/admin/courts", headers=h).status_code == 200
    # users endpoint blocked for manager
    assert client.get("/api/v1/admin/users", headers=h).status_code == 403
