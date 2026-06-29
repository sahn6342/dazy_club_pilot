"""
Pricing + promo-code tests: slot price fields, block discounts, rule PATCH,
promo CRUD, and promo application/validation at booking time.
"""
from datetime import date, timedelta


# ── helpers ──────────────────────────────────────────────────────────────────

def _offset(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _future() -> str:
    return _offset(1)


def _weekday(day: str) -> int:
    return date.fromisoformat(day).weekday()


def _slots(client, sport, day):
    return client.get(f"/api/v1/slots?sport={sport}&date={day}").json()


def _first_available(client, sport, day):
    return next(s for s in _slots(client, sport, day) if s["available"])


def _patch_rule(client, headers, court_id, weekday, open_time, body):
    rules = client.get(f"/api/v1/admin/schedule/rules?court_id={court_id}", headers=headers).json()
    rule = next(r for r in rules if r["weekday"] == weekday and r["open_time"] == open_time)
    return client.patch(f"/api/v1/admin/schedule/rules/{rule['id']}", json=body, headers=headers)


def _book(client, sport, day, promo=None, contact="9100000001", slot=None):
    slot = slot or _first_available(client, sport, day)
    payload = {
        "name": "Pricing Tester", "contact": contact,
        "slotId": slot["id"], "sportSlug": sport,
        "date": slot["date"], "startTime": slot["startTime"], "players": 1,
    }
    if promo:
        payload["promoCode"] = promo
    return client.post("/api/v1/bookings", json=payload), slot


def _create_promo(client, headers, **kwargs):
    body = {"code": "TEST", "kind": "percent", "value": 10}
    body.update(kwargs)
    return client.post("/api/v1/admin/promos", json=body, headers=headers)


# ── 1-5: slot price fields + rule PATCH ──────────────────────────────────────

def test_slots_include_price_fields(client):
    s = _first_available(client, "cricket", _future())
    assert "price" in s and "discountPercent" in s and "finalPrice" in s
    assert s["price"] == 1200.0  # seeded default
    assert s["finalPrice"] == 1200.0


def test_block_discount_math(client, auth_headers):
    day = _future()
    wd = _weekday(day)
    r = _patch_rule(client, auth_headers, "court-cricket", wd, "06:00",
                    {"price": 800, "discount_percent": 20})
    assert r.status_code == 200, r.text
    s = next(s for s in _slots(client, "cricket", day) if s["startTime"] == "06:00")
    assert s["price"] == 800.0
    assert s["discountPercent"] == 20
    assert s["finalPrice"] == 640.0


def test_price_null_is_free(client, auth_headers):
    day = _future()
    wd = _weekday(day)
    _patch_rule(client, auth_headers, "court-cricket", wd, "06:00", {"price": None})
    s = next(s for s in _slots(client, "cricket", day) if s["startTime"] == "06:00")
    assert s["price"] is None
    assert s["finalPrice"] is None


def test_rule_patch_hours_changes_slot_count(client, auth_headers):
    day = _future()
    wd = _weekday(day)
    before = len(_slots(client, "cricket", day))
    r = _patch_rule(client, auth_headers, "court-cricket", wd, "06:00", {"close_time": "08:00"})
    assert r.status_code == 200
    after = len(_slots(client, "cricket", day))
    assert after < before  # morning block 06-12 (6 slots) -> 06-08 (2 slots)


def test_rule_patch_404(client, auth_headers):
    r = client.patch("/api/v1/admin/schedule/rules/nope", json={"price": 10}, headers=auth_headers)
    assert r.status_code == 404


# ── 6-7: promo CRUD ───────────────────────────────────────────────────────────

def test_promo_crud(client, auth_headers):
    r = _create_promo(client, auth_headers, code="CRUD5", kind="percent", value=5)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["code"] == "CRUD5"

    listed = client.get("/api/v1/admin/promos", headers=auth_headers).json()
    assert any(p["code"] == "CRUD5" for p in listed)

    r = client.patch(f"/api/v1/admin/promos/{pid}", json={"active": False}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["active"] is False

    r = client.delete(f"/api/v1/admin/promos/{pid}", headers=auth_headers)
    assert r.status_code == 204
    assert client.delete(f"/api/v1/admin/promos/{pid}", headers=auth_headers).status_code == 404


def test_promo_duplicate_code_409(client, auth_headers):
    assert _create_promo(client, auth_headers, code="DUP1").status_code == 201
    assert _create_promo(client, auth_headers, code="DUP1").status_code == 409


# ── 8-10: promo application math ──────────────────────────────────────────────

def test_promo_percent_applied(client, auth_headers):
    # WELCOME10 is seeded (percent 10). cricket base 1200 -> 1080.
    r, slot = _book(client, "cricket", _future(), promo="WELCOME10")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["price"] == 1080.0
    assert body["promoCode"] == "WELCOME10"


def test_promo_flat_applied(client, auth_headers):
    # FLAT100 seeded (flat 100). 1200 -> 1100.
    r, _ = _book(client, "cricket", _future(), promo="FLAT100")
    assert r.status_code == 201, r.text
    assert r.json()["price"] == 1100.0


def test_promo_flat_floor_zero(client, auth_headers):
    _create_promo(client, auth_headers, code="HUGE", kind="flat", value=99999)
    r, _ = _book(client, "cricket", _future(), promo="HUGE")
    assert r.status_code == 201
    assert r.json()["price"] == 0.0


# ── 11-16: promo validation failures (400) ───────────────────────────────────

def test_promo_invalid_code_400(client):
    r, _ = _book(client, "cricket", _future(), promo="NOPECODE")
    assert r.status_code == 400


def test_promo_inactive_400(client, auth_headers):
    _create_promo(client, auth_headers, code="OFF", kind="percent", value=10, active=False)
    r, _ = _book(client, "cricket", _future(), promo="OFF")
    assert r.status_code == 400


def test_promo_expired_400(client, auth_headers):
    _create_promo(client, auth_headers, code="OLD", kind="percent", value=10, valid_to=_offset(-1))
    r, _ = _book(client, "cricket", _future(), promo="OLD")
    assert r.status_code == 400


def test_promo_not_yet_valid_400(client, auth_headers):
    _create_promo(client, auth_headers, code="SOON", kind="percent", value=10, valid_from=_offset(2))
    r, _ = _book(client, "cricket", _future(), promo="SOON")
    assert r.status_code == 400


def test_promo_exhausted_400(client, auth_headers):
    _create_promo(client, auth_headers, code="ONCE", kind="percent", value=10, max_uses=1)
    slots = [s for s in _slots(client, "cricket", _future()) if s["available"]]
    r1, _ = _book(client, "cricket", _future(), promo="ONCE", slot=slots[0])
    assert r1.status_code == 201
    r2, _ = _book(client, "cricket", _future(), promo="ONCE", slot=slots[1], contact="9100000002")
    assert r2.status_code == 400


def test_promo_wrong_sport_400(client, auth_headers):
    _create_promo(client, auth_headers, code="BADO", kind="percent", value=10, sport_slug="badminton")
    r, _ = _book(client, "cricket", _future(), promo="BADO")
    assert r.status_code == 400


# ── 17-20: persistence + admin exposure ──────────────────────────────────────

def test_promo_increments_used_count(client, auth_headers):
    _book(client, "cricket", _future(), promo="WELCOME10")
    promos = client.get("/api/v1/admin/promos", headers=auth_headers).json()
    welcome = next(p for p in promos if p["code"] == "WELCOME10")
    assert welcome["used_count"] == 1


def test_booking_without_promo_stores_final_price(client):
    r, slot = _book(client, "cricket", _future())
    assert r.status_code == 201
    assert r.json()["price"] == slot["finalPrice"]
    assert r.json()["promoCode"] is None


def test_free_slot_with_promo_no_error(client, auth_headers):
    day = _future()
    wd = _weekday(day)
    _patch_rule(client, auth_headers, "court-cricket", wd, "06:00", {"price": None})
    free = next(s for s in _slots(client, "cricket", day) if s["startTime"] == "06:00")
    r, _ = _book(client, "cricket", day, promo="WELCOME10", slot=free)
    assert r.status_code == 201
    assert r.json()["price"] is None


def test_admin_bookings_exposes_price_and_promo(client, auth_headers):
    _book(client, "cricket", _future(), promo="WELCOME10")
    rows = client.get("/api/v1/admin/bookings", headers=auth_headers).json()
    assert rows
    row = rows[0]
    assert "price" in row and "promo_code" in row
    assert row["price"] == 1080.0
    assert row["promo_code"] == "WELCOME10"


# ── /promos/validate endpoint ──────────────────────────────────────────────────

def test_validate_valid_percent_promo(client):
    r = client.get("/api/v1/promos/validate?code=WELCOME10&sport=cricket&amount=1200")
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["code"] == "WELCOME10"
    assert body["kind"] == "percent"
    assert body["value"] == 10.0
    assert body["discountedAmount"] == 1080.0
    assert body["savedAmount"] == 120.0


def test_validate_flat_promo(client):
    r = client.get("/api/v1/promos/validate?code=FLAT100&sport=cricket&amount=1200")
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["discountedAmount"] == 1100.0
    assert body["savedAmount"] == 100.0


def test_validate_no_amount_returns_null_discounted(client):
    r = client.get("/api/v1/promos/validate?code=WELCOME10&sport=cricket")
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["discountedAmount"] is None
    assert body["savedAmount"] is None


def test_validate_invalid_code(client):
    r = client.get("/api/v1/promos/validate?code=NOPECODE&sport=cricket&amount=1200")
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert "error" in body
    assert body["code"] == "NOPECODE"


def test_validate_inactive_promo(client, auth_headers):
    client.patch(
        "/api/v1/admin/promos/" + _get_promo_id(client, auth_headers, "WELCOME10"),
        json={"active": False}, headers=auth_headers,
    )
    r = client.get("/api/v1/promos/validate?code=WELCOME10&sport=cricket&amount=1200")
    assert r.json()["valid"] is False
    assert "inactive" in r.json()["error"].lower()


def test_validate_expired_promo(client, auth_headers):
    from datetime import date, timedelta
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    client.post("/api/v1/admin/promos", json={
        "code": "EXPIRED99", "kind": "percent", "value": 5, "valid_to": yesterday
    }, headers=auth_headers)
    r = client.get("/api/v1/promos/validate?code=EXPIRED99&sport=cricket&amount=1200")
    assert r.json()["valid"] is False
    assert "expired" in r.json()["error"].lower()


def test_validate_wrong_sport(client, auth_headers):
    client.post("/api/v1/admin/promos", json={
        "code": "BADSPORT", "kind": "percent", "value": 10, "sport_slug": "badminton"
    }, headers=auth_headers)
    r = client.get("/api/v1/promos/validate?code=BADSPORT&sport=cricket&amount=1200")
    assert r.json()["valid"] is False


def test_validate_flat_floor_zero(client):
    r = client.get("/api/v1/promos/validate?code=FLAT100&sport=cricket&amount=50")
    body = r.json()
    assert body["valid"] is True
    assert body["discountedAmount"] == 0.0
    assert body["savedAmount"] == 50.0


def test_validate_does_not_increment_used_count(client, auth_headers):
    r_before = client.get("/api/v1/admin/promos", headers=auth_headers).json()
    before = next(p for p in r_before if p["code"] == "WELCOME10")["used_count"]
    client.get("/api/v1/promos/validate?code=WELCOME10&sport=cricket&amount=1200")
    client.get("/api/v1/promos/validate?code=WELCOME10&sport=cricket&amount=1200")
    r_after = client.get("/api/v1/admin/promos", headers=auth_headers).json()
    after = next(p for p in r_after if p["code"] == "WELCOME10")["used_count"]
    assert after == before  # validate never increments


def _get_promo_id(client, auth_headers, code):
    promos = client.get("/api/v1/admin/promos", headers=auth_headers).json()
    return next(p["id"] for p in promos if p["code"] == code)
