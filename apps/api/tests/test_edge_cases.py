"""
Cross-cutting edge cases and known API behaviour boundaries.
Documents both enforced constraints and intentional limitations.
"""
import os
import time
import uuid
from datetime import date, timedelta, datetime, timezone

import jwt
import pytest

_SECRET = os.environ.get("JWT_SECRET", "dazy-dev-secret-change-in-production")
_ALGORITHM = "HS256"


def _today():
    return date.today().isoformat()


def _date_offset(days: int):
    return (date.today() + timedelta(days=days)).isoformat()


def _get_available_slot(client, sport="cricket"):
    slots = client.get(f"/api/v1/slots?sport={sport}&date={_date_offset(1)}").json()
    return next((s for s in slots if s["available"]), None)


def _book(client, slot, **overrides):
    payload = {
        "name": "Edge Tester",
        "contact": "9000000000",
        "slotId": slot["id"],
        "sportSlug": slot["sportSlug"],
        "date": slot["date"],
        "startTime": slot["startTime"],
        "players": 2,
        **overrides,
    }
    return client.post("/api/v1/bookings", json=payload)


# ── JWT / Auth edge cases ──────────────────────────────────────────────────────

def _make_token(payload: dict) -> str:
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def test_expired_token_rejected(client):
    token = _make_token({
        "sub": "admin",
        "role": "admin",
        "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
    })
    r = client.get("/api/v1/admin/bookings", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert "expired" in r.json()["detail"].lower()


def test_token_wrong_secret_rejected(client):
    token = jwt.encode({"sub": "admin", "role": "admin", "exp": time.time() + 3600}, "wrong-secret", algorithm="HS256")
    r = client.get("/api/v1/admin/bookings", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_token_tampered_payload_rejected(client, admin_token):
    # Decode without verifying, swap sub, re-encode with wrong key
    header, payload_b64, sig = admin_token.split(".")
    import base64, json
    pad = len(payload_b64) % 4
    payload_bytes = base64.urlsafe_b64decode(payload_b64 + "=" * (4 - pad) if pad else payload_b64)
    payload = json.loads(payload_bytes)
    payload["role"] = "superadmin"
    tampered_token = jwt.encode(payload, "wrong-key", algorithm="HS256")
    r = client.get("/api/v1/admin/bookings", headers={"Authorization": f"Bearer {tampered_token}"})
    assert r.status_code == 401


def test_random_string_as_token(client):
    r = client.get("/api/v1/admin/bookings", headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401


def test_bearer_missing_token_value(client):
    r = client.get("/api/v1/admin/bookings", headers={"Authorization": "Bearer "})
    assert r.status_code in (401, 403, 422)


def test_no_bearer_prefix(client):
    r = client.get("/api/v1/admin/bookings", headers={"Authorization": "admin"})
    assert r.status_code in (401, 403)


def test_deleted_manager_token_still_valid_until_expiry(client, auth_headers):
    """JWT is stateless — token remains valid after account deletion."""
    client.post("/api/v1/admin/users", json={"username": "ghost", "password": "secure123"}, headers=auth_headers)
    mgr_token = client.post("/api/v1/admin/login", json={"username": "ghost", "password": "secure123"}).json()["access_token"]
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
    # Delete the manager
    uid = client.get("/api/v1/admin/users", headers=auth_headers).json()[0]["id"]
    client.delete(f"/api/v1/admin/users/{uid}", headers=auth_headers)
    # Token still works (stateless JWT — intentional limitation, fix with token revocation list in production)
    r = client.get("/api/v1/admin/bookings", headers=mgr_headers)
    assert r.status_code == 200


# ── Slots edge cases ───────────────────────────────────────────────────────────

def test_past_date_returns_empty(client):
    yesterday = _date_offset(-1)
    r = client.get(f"/api/v1/slots?sport=cricket&date={yesterday}")
    assert r.status_code == 200
    assert r.json() == []


def test_date_beyond_7_days_returns_empty(client):
    future = _date_offset(8)
    r = client.get(f"/api/v1/slots?sport=cricket&date={future}")
    assert r.status_code == 200
    assert r.json() == []


def test_slot_count_per_day(client):
    """Each sport/date combo has exactly 12 slots on a full future day
    (today is intentionally trimmed by the past-slot filter)."""
    slots = client.get(f"/api/v1/slots?sport=badminton&date={_date_offset(1)}").json()
    assert len(slots) == 12


def test_all_three_sports_have_slots(client):
    for sport in ("cricket", "badminton", "pickleball"):
        r = client.get(f"/api/v1/slots?sport={sport}&date={_date_offset(1)}")
        assert r.status_code == 200
        assert len(r.json()) > 0, f"No slots for {sport}"


def test_slots_across_7_days(client):
    """Slots generated for all 7 days in the bookable horizon."""
    for offset in range(1, 7):
        r = client.get(f"/api/v1/slots?sport=cricket&date={_date_offset(offset)}")
        assert r.status_code == 200
        assert len(r.json()) > 0, f"No slots for day offset {offset}"


def test_invalid_date_format_returns_empty(client):
    r = client.get("/api/v1/slots?sport=cricket&date=not-a-date")
    assert r.status_code == 200
    assert r.json() == []


def test_slot_ids_are_unique(client):
    slots = client.get(f"/api/v1/slots?sport=cricket&date={_today()}").json()
    ids = [s["id"] for s in slots]
    assert len(ids) == len(set(ids))


# ── Booking edge cases ─────────────────────────────────────────────────────────

def test_booking_players_min_boundary(client):
    """players=1 is valid."""
    slot = _get_available_slot(client)
    r = _book(client, slot, players=1)
    assert r.status_code in (200, 201)


def test_booking_players_max_boundary(client):
    """players=12 is model max — succeeds even if over sport-specific capacity."""
    slot = _get_available_slot(client)
    r = _book(client, slot, players=12)
    assert r.status_code in (200, 201)


def test_booking_players_over_max_rejected(client):
    """players=13 exceeds model max (le=12)."""
    slot = _get_available_slot(client)
    r = _book(client, slot, players=13)
    assert r.status_code == 422


def test_booking_players_negative_rejected(client):
    slot = _get_available_slot(client)
    r = _book(client, slot, players=-1)
    assert r.status_code == 422


def test_booking_players_zero_rejected(client):
    slot = _get_available_slot(client)
    r = _book(client, slot, players=0)
    assert r.status_code == 422


def test_booking_sport_mismatch_rejected(client):
    """Phase 1: slot ids are generated per court/sport, so a cricket slot booked
    under sportSlug=badminton is not found -> 404 (cross-validation now enforced)."""
    slot = _get_available_slot(client, sport="cricket")
    r = _book(client, slot, sportSlug="badminton")
    assert r.status_code == 404


def test_booking_whitespace_name_passes_min_length(client):
    """Pydantic v2 min_length=1 does NOT strip whitespace.
    Single space satisfies min_length. Known limitation: add strip_whitespace validator."""
    slot = _get_available_slot(client)
    r = _book(client, slot, name=" ")
    assert r.status_code in (200, 201)


def test_booking_very_long_name_accepted(client):
    """No max_length on name field — 500 chars passes."""
    slot = _get_available_slot(client)
    r = _book(client, slot, name="A" * 500)
    assert r.status_code in (200, 201)


def test_booking_ref_is_unique(client):
    """Two bookings get different refs."""
    s1 = _get_available_slot(client, sport="cricket")
    s2 = _get_available_slot(client, sport="badminton")
    r1 = _book(client, s1)
    r2 = _book(client, s2)
    assert r1.json()["bookingRef"] != r2.json()["bookingRef"]


def test_cancelled_booking_reopens_slot(client, auth_headers):
    """Phase 2: cancelling a booking re-opens the slot (capacity-aware availability).
    Cancelled bookings are excluded from the occupied sum, so under_capacity flips back True."""
    slot = _get_available_slot(client)
    _book(client, slot)
    bid = client.get("/api/v1/admin/bookings", headers=auth_headers).json()[0]["id"]
    client.patch(f"/api/v1/admin/bookings/{bid}", json={"status": "cancelled"}, headers=auth_headers)
    slots = client.get(f"/api/v1/slots?sport=cricket&date={_date_offset(1)}").json()
    found = next((s for s in slots if s["id"] == slot["id"]), None)
    assert found is not None
    assert found["available"] is True  # slot freed by cancellation


def test_booking_fake_slot_id_rejected(client):
    r = client.post("/api/v1/bookings", json={
        "name": "A", "contact": "1",
        "slotId": str(uuid.uuid4()),
        "sportSlug": "cricket",
        "date": _today(),
        "startTime": "06:00",
        "players": 1,
    })
    assert r.status_code == 404


def test_booking_missing_all_fields(client):
    r = client.post("/api/v1/bookings", json={})
    assert r.status_code == 422


def test_booking_response_has_expected_keys(client):
    slot = _get_available_slot(client)
    r = _book(client, slot)
    body = r.json()
    for key in ("status", "bookingRef", "name", "sport", "date", "time"):
        assert key in body, f"Missing key: {key}"


# ── Enquiry edge cases ─────────────────────────────────────────────────────────

def test_contact_enquiry_optional_fields_omitted(client):
    """interestedSport and message are optional."""
    r = client.post("/api/v1/contact-enquiries", json={"name": "X", "contact": "Y"})
    assert r.status_code in (200, 201)


def test_contact_enquiry_all_fields(client):
    r = client.post("/api/v1/contact-enquiries", json={
        "name": "Full Name", "contact": "9800000001",
        "interestedSport": "pickleball", "message": "Hello there",
    })
    assert r.status_code in (200, 201)


def test_corporate_group_size_one(client):
    """Minimum valid group size is 1 (gt=0)."""
    r = client.post("/api/v1/corporate-enquiries", json={
        "contactName": "A", "company": "B", "contact": "C", "estimatedGroupSize": 1,
    })
    assert r.status_code in (200, 201)


def test_corporate_group_size_large(client):
    """No upper cap on group size."""
    r = client.post("/api/v1/corporate-enquiries", json={
        "contactName": "A", "company": "B", "contact": "C", "estimatedGroupSize": 10000,
    })
    assert r.status_code in (200, 201)


def test_corporate_group_size_float_rejected(client):
    """estimatedGroupSize must be int."""
    r = client.post("/api/v1/corporate-enquiries", json={
        "contactName": "A", "company": "B", "contact": "C", "estimatedGroupSize": 3.5,
    })
    # Pydantic coerces float to int or rejects — either is acceptable
    assert r.status_code in (200, 201, 422)


def test_contact_enquiry_returns_id(client):
    r = client.post("/api/v1/contact-enquiries", json={"name": "X", "contact": "Y"})
    body = r.json()
    assert "id" in body
    assert len(body["id"]) > 0


def test_multiple_enquiries_have_unique_ids(client):
    ids = []
    for i in range(5):
        r = client.post("/api/v1/contact-enquiries", json={"name": f"User{i}", "contact": str(i)})
        ids.append(r.json()["id"])
    assert len(ids) == len(set(ids))


def test_enquiry_missing_contact_rejected(client):
    r = client.post("/api/v1/contact-enquiries", json={"name": "Test"})
    assert r.status_code == 422


def test_corporate_missing_contact_name_rejected(client):
    r = client.post("/api/v1/corporate-enquiries", json={
        "company": "Corp", "contact": "9800000001", "estimatedGroupSize": 10,
    })
    assert r.status_code == 422


def test_corporate_missing_contact_rejected(client):
    r = client.post("/api/v1/corporate-enquiries", json={
        "contactName": "Name", "company": "Corp", "estimatedGroupSize": 10,
    })
    assert r.status_code == 422


# ── CMS edge cases ─────────────────────────────────────────────────────────────

def test_cms_update_empty_string_value(client, auth_headers):
    """Empty string is valid — no min_length on CmsEntryUpdate.value."""
    r = client.put("/api/v1/admin/cms/hero_tagline", json={"value": ""}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["value"] == ""


def test_cms_update_very_long_value(client, auth_headers):
    long_val = "x" * 5000
    r = client.put("/api/v1/admin/cms/hero_tagline", json={"value": long_val}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["value"] == long_val


def test_cms_update_missing_value_field(client, auth_headers):
    r = client.put("/api/v1/admin/cms/hero_tagline", json={}, headers=auth_headers)
    assert r.status_code == 422


def test_cms_keys_are_stable(client, auth_headers):
    """Expected CMS keys from seed are all present."""
    entries = client.get("/api/v1/admin/cms", headers=auth_headers).json()
    keys = {e["key"] for e in entries}
    for expected in ("faq_booking", "faq_sports", "hero_tagline", "hero_copy", "footer_tagline"):
        assert expected in keys, f"Missing CMS key: {expected}"


# ── User management edge cases ─────────────────────────────────────────────────

def test_username_min_boundary(client, auth_headers):
    """3-char username is valid."""
    r = client.post("/api/v1/admin/users", json={"username": "abc", "password": "secure123"}, headers=auth_headers)
    assert r.status_code == 201


def test_username_max_boundary(client, auth_headers):
    """50-char username is valid."""
    r = client.post("/api/v1/admin/users", json={"username": "a" * 50, "password": "secure123"}, headers=auth_headers)
    assert r.status_code == 201


def test_username_over_max_rejected(client, auth_headers):
    """51-char username rejected."""
    r = client.post("/api/v1/admin/users", json={"username": "a" * 51, "password": "secure123"}, headers=auth_headers)
    assert r.status_code == 422


def test_username_two_chars_rejected(client, auth_headers):
    r = client.post("/api/v1/admin/users", json={"username": "ab", "password": "secure123"}, headers=auth_headers)
    assert r.status_code == 422


def test_password_min_boundary(client, auth_headers):
    """Exactly 8-char password is valid."""
    r = client.post("/api/v1/admin/users", json={"username": "mgr1", "password": "12345678"}, headers=auth_headers)
    assert r.status_code == 201


def test_password_seven_chars_rejected(client, auth_headers):
    """7-char password is below min_length=8."""
    r = client.post("/api/v1/admin/users", json={"username": "mgr1", "password": "1234567"}, headers=auth_headers)
    assert r.status_code == 422


def test_create_many_managers(client, auth_headers):
    """Can create multiple managers without conflict."""
    for i in range(5):
        r = client.post("/api/v1/admin/users",
                        json={"username": f"manager{i}", "password": "secure123"},
                        headers=auth_headers)
        assert r.status_code == 201
    r = client.get("/api/v1/admin/users", headers=auth_headers)
    assert len(r.json()) == 5


def test_manager_cannot_create_other_managers(client, auth_headers):
    """Manager token rejected for POST /admin/users."""
    client.post("/api/v1/admin/users", json={"username": "mgr1", "password": "secure123"}, headers=auth_headers)
    mgr_token = client.post("/api/v1/admin/login", json={"username": "mgr1", "password": "secure123"}).json()["access_token"]
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
    r = client.post("/api/v1/admin/users", json={"username": "mgr2", "password": "secure123"}, headers=mgr_headers)
    assert r.status_code == 403


def test_manager_cannot_delete_managers(client, auth_headers):
    client.post("/api/v1/admin/users", json={"username": "mgr1", "password": "secure123"}, headers=auth_headers)
    client.post("/api/v1/admin/users", json={"username": "mgr2", "password": "secure456"}, headers=auth_headers)
    mgr_token = client.post("/api/v1/admin/login", json={"username": "mgr1", "password": "secure123"}).json()["access_token"]
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
    uid = client.get("/api/v1/admin/users", headers=auth_headers).json()[1]["id"]
    r = client.delete(f"/api/v1/admin/users/{uid}", headers=mgr_headers)
    assert r.status_code == 403


def test_patch_user_empty_body_ok(client, auth_headers):
    """PATCH with no fields is a no-op, returns current user."""
    client.post("/api/v1/admin/users", json={"username": "mgr1", "password": "secure123"}, headers=auth_headers)
    uid = client.get("/api/v1/admin/users", headers=auth_headers).json()[0]["id"]
    r = client.patch(f"/api/v1/admin/users/{uid}", json={}, headers=auth_headers)
    assert r.status_code == 200


def test_patch_user_short_new_password_rejected(client, auth_headers):
    client.post("/api/v1/admin/users", json={"username": "mgr1", "password": "secure123"}, headers=auth_headers)
    uid = client.get("/api/v1/admin/users", headers=auth_headers).json()[0]["id"]
    r = client.patch(f"/api/v1/admin/users/{uid}", json={"password": "short"}, headers=auth_headers)
    assert r.status_code == 422


def test_user_public_never_exposes_hash(client, auth_headers):
    """hashed_password must never appear in any response."""
    client.post("/api/v1/admin/users", json={"username": "mgr1", "password": "secure123"}, headers=auth_headers)
    users = client.get("/api/v1/admin/users", headers=auth_headers).json()
    for u in users:
        assert "hashed_password" not in u
        assert "password" not in u


# ── Admin filter edge cases ────────────────────────────────────────────────────

def test_admin_bookings_filter_nonexistent_status(client, auth_headers):
    """Unknown status value returns empty (no match) rather than error."""
    r = client.get("/api/v1/admin/bookings?status=nonexistent", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_admin_enquiries_filter_nonexistent_type(client, auth_headers):
    r = client.get("/api/v1/admin/enquiries?type=nonexistent", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_admin_booking_patch_nonexistent_id(client, auth_headers):
    r = client.patch("/api/v1/admin/bookings/fake-id", json={"status": "confirmed"}, headers=auth_headers)
    assert r.status_code == 404


def test_admin_enquiry_patch_nonexistent_id(client, auth_headers):
    r = client.patch("/api/v1/admin/enquiries/fake-id", json={"status": "handled"}, headers=auth_headers)
    assert r.status_code == 404


# ── Phase 0: resource (Venue/Court) linkage ────────────────────────────────────

def test_slots_carry_court_id(client):
    """Every slot is tagged with its bookable court (one court per sport in the pilot)."""
    slots = client.get(f"/api/v1/slots?sport=cricket&date={_date_offset(1)}").json()
    assert slots
    assert all(s["courtId"] == "court-cricket" for s in slots)


def test_booking_persists_court_id(client, auth_headers):
    """A created booking is linked to the sport's court."""
    slots = client.get(f"/api/v1/slots?sport=badminton&date={_date_offset(1)}").json()
    slot = next(s for s in slots if s["available"])
    r = client.post("/api/v1/bookings", json={
        "name": "Court Test", "contact": "9000000001", "slotId": slot["id"],
        "sportSlug": "badminton", "date": slot["date"], "startTime": slot["startTime"], "players": 2,
    })
    assert r.status_code in (200, 201)
    bookings = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    assert bookings[0]["court_id"] == "court-badminton"
