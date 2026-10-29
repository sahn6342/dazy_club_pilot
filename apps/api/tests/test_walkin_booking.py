"""Counter (walk-in) bookings: staff book a slot and take cash/UPI, no payment gateway."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import deps
from services import availability_service


def _tomorrow():
    return (date.today() + timedelta(days=1)).isoformat()


def _slots(client, auth_headers, sport="cricket", day=None):
    r = client.get(f"/api/v1/admin/slots?sport={sport}&date={day or _tomorrow()}", headers=auth_headers)
    assert r.status_code == 200, r.text
    return [s for s in r.json() if s["available"]]


def _walkin(client, auth_headers, slot_ids, mode="cash", sport="cricket", day=None, **extra):
    body = {"name": "Ravi", "contact": "9123456780", "slotIds": slot_ids, "sportSlug": sport,
            "date": day or _tomorrow(), "players": 4, "paymentMode": mode, **extra}
    return client.post("/api/v1/admin/bookings/walkin", json=body, headers=auth_headers)


def _admin_row(client, auth_headers, ref):
    items = client.get("/api/v1/admin/bookings?limit=100", headers=auth_headers).json()["items"]
    return next(x for x in items if x["bookingRef"] == ref)


def test_cash_walkin_is_confirmed_and_paid_without_a_gateway_payment(client, auth_headers):
    slot = _slots(client, auth_headers)[0]
    r = _walkin(client, auth_headers, [slot["id"]], "cash")
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["status"] == "confirmed" and b["paymentStatus"] == "paid" and b["paymentMode"] == "cash"
    assert "checkout" not in b
    assert deps.booking_payment_repo.list_by_ref(b["bookingRef"]) == []
    row = _admin_row(client, auth_headers, b["bookingRef"])
    assert row["source"] == "counter" and row["payment_mode"] == "cash" and row["created_by"]
    assert row["status"] == "confirmed" and row["paymentStatus"] == "paid"


def test_upi_walkin_keeps_the_reference(client, auth_headers):
    slot = _slots(client, auth_headers)[0]
    b = _walkin(client, auth_headers, [slot["id"]], "upi", reference="  UTR123456  ").json()
    assert b["paymentMode"] == "upi" and b["reference"] == "UTR123456"
    assert _admin_row(client, auth_headers, b["bookingRef"])["payment_reference"] == "UTR123456"


def test_walkin_blocks_the_slot_for_everyone(client, auth_headers):
    slot = _slots(client, auth_headers)[0]
    assert _walkin(client, auth_headers, [slot["id"]]).status_code == 201
    public = client.get(f"/api/v1/slots?sport=cricket&date={_tomorrow()}").json()
    assert next(s for s in public if s["id"] == slot["id"])["available"] is False
    again = _walkin(client, auth_headers, [slot["id"]])
    assert again.status_code == 409 and again.json()["code"] == "slot_unavailable"


def test_multi_slot_walkin_creates_one_booking_with_all_slots(client, auth_headers):
    slots = _slots(client, auth_headers)
    pair = next((a, b) for a, b in zip(slots, slots[1:]) if a["endTime"] == b["startTime"] and a["courtId"] == b["courtId"])
    b = _walkin(client, auth_headers, [pair[0]["id"], pair[1]["id"]]).json()
    assert b["slotCount"] == 2 and b["startTime"] == pair[0]["startTime"] and b["endTime"] == pair[1]["endTime"]
    assert len(deps.booking_repo.get_by_ref(b["bookingRef"])) == 2


def test_non_consecutive_slots_are_rejected(client, auth_headers):
    slots = _slots(client, auth_headers)
    r = _walkin(client, auth_headers, [slots[0]["id"], slots[2]["id"]])
    assert r.status_code == 400 and r.json()["code"] == "slots_not_consecutive"


def test_payment_mode_must_be_cash_or_upi(client, auth_headers):
    slot = _slots(client, auth_headers)[0]
    assert _walkin(client, auth_headers, [slot["id"]], "card").status_code == 422
    assert _walkin(client, auth_headers, [slot["id"]], "razorpay").status_code == 422


def test_name_and_valid_phone_are_required(client, auth_headers):
    slot = _slots(client, auth_headers)[0]
    assert _walkin(client, auth_headers, [slot["id"]], contact="12345").status_code == 422
    assert _walkin(client, auth_headers, [slot["id"]], name="").status_code == 422


def test_walkin_requires_an_admin(client):
    r = client.post("/api/v1/admin/bookings/walkin", json={})
    assert r.status_code in (401, 403)
    assert client.get("/api/v1/admin/slots?sport=cricket&date=2030-01-01").status_code in (401, 403)


def test_walkin_is_audited_with_actor_and_mode(client, auth_headers):
    slot = _slots(client, auth_headers)[0]
    b = _walkin(client, auth_headers, [slot["id"]], "upi", reference="R1").json()
    items, _ = deps.audit_repo.query(limit=200)
    rows = [r for r in items if r.action == "booking.walkin_create"]
    assert len(rows) == 1
    assert b["bookingRef"] in str(rows[0].detail) and "upi" in str(rows[0].detail)


def test_unknown_promo_is_rejected_and_nothing_is_booked(client, auth_headers):
    slot = _slots(client, auth_headers)[0]
    r = _walkin(client, auth_headers, [slot["id"]], promoCode="NOPE")
    assert r.status_code == 400 and r.json()["code"] == "promo_invalid"
    assert next(s for s in _slots(client, auth_headers) if s["id"] == slot["id"])


def test_counter_booking_can_be_cancelled_and_frees_the_slot(client, auth_headers):
    slot = _slots(client, auth_headers)[0]
    b = _walkin(client, auth_headers, [slot["id"]]).json()
    r = client.post(f"/api/v1/admin/bookings/{b['id']}/cancel-and-refund", json={"amount": 0}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert any(s["id"] == slot["id"] for s in _slots(client, auth_headers))


def test_csv_export_has_source_and_payment_mode(client, auth_headers):
    slot = _slots(client, auth_headers)[0]
    _walkin(client, auth_headers, [slot["id"]], "upi")
    text = client.get("/api/v1/admin/bookings/export", headers=auth_headers).text
    assert "Source" in text and "Payment Mode" in text and "counter" in text and "upi" in text


# ── the hour in progress ────────────────────────────────────────────────────

@pytest.fixture
def mid_slot(client, auth_headers, monkeypatch):
    """Freeze 'now' ten minutes into tomorrow's second slot (tomorrow becomes 'today'), so the first one has ended."""
    first, probe = _slots(client, auth_headers)[:2]
    tz = ZoneInfo("Asia/Kolkata")
    now = datetime.fromisoformat(f"{probe['date']}T{probe['startTime']}:00").replace(tzinfo=tz) + timedelta(minutes=10)

    class FrozenDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz) if tz else now

    monkeypatch.setattr(availability_service, "datetime", FrozenDT)
    return {"ended": first, "current": probe}


def test_slot_in_progress_is_bookable_at_the_counter_but_not_online(client, auth_headers, mid_slot):
    cur = mid_slot["current"]
    public = client.get(f"/api/v1/slots?sport=cricket&date={cur['date']}").json()
    assert all(s["id"] != cur["id"] for s in public)  # online: already started, hidden
    assert any(s["id"] == cur["id"] and s["available"] for s in _slots(client, auth_headers, day=cur["date"]))
    r = _walkin(client, auth_headers, [cur["id"]], day=cur["date"])
    assert r.status_code == 201, r.text


def test_ended_slot_is_not_bookable_at_the_counter(client, auth_headers, mid_slot):
    ended = mid_slot["ended"]
    assert all(s["id"] != ended["id"] for s in _slots(client, auth_headers, day=ended["date"]))
    r = _walkin(client, auth_headers, [ended["id"]], day=ended["date"])
    assert r.status_code in (404, 409), r.text


# ── part payment (advance) ──────────────────────────────────────────────────

def _priced_slot(client, auth_headers):
    """A slot that has a price (the walk-in tests above work on whatever the seed gives)."""
    for sport in ("badminton", "pickleball", "cricket"):
        for s in _slots(client, auth_headers, sport=sport):
            if s["finalPrice"]:
                return sport, s
    pytest.skip("no priced slot in the seed")


def _advance_walkin(client, auth_headers, paid, mode="upi", **extra):
    sport, slot = _priced_slot(client, auth_headers)
    r = _walkin(client, auth_headers, [slot["id"]], mode, sport=sport, amountPaid=paid, **extra)
    return r, slot


def test_part_payment_is_stored_as_an_advance_with_a_balance(client, auth_headers):
    sport, slot = _priced_slot(client, auth_headers)
    price = slot["finalPrice"]
    paid = round(price / 4, 2)
    r = _walkin(client, auth_headers, [slot["id"]], "upi", sport=sport, amountPaid=paid)
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["amountPaid"] == paid and b["balanceDue"] == round(price - paid, 2) and b["paymentStatus"] == "paid"
    row = _admin_row(client, auth_headers, b["bookingRef"])
    assert row["depositAmount"] == paid and row["source"] == "counter" and row["payment_mode"] == "upi"
    assert row["status"] == "confirmed" and row["balance_collected"] == 0


def test_full_amount_or_no_amount_is_just_full_payment(client, auth_headers):
    sport, slot = _priced_slot(client, auth_headers)
    r = _walkin(client, auth_headers, [slot["id"]], sport=sport, amountPaid=slot["finalPrice"])
    assert r.status_code == 201 and r.json()["balanceDue"] == 0.0
    assert _admin_row(client, auth_headers, r.json()["bookingRef"])["depositAmount"] is None
    other = next(s for s in _slots(client, auth_headers, sport=sport) if s["id"] != slot["id"] and s["finalPrice"])
    r2 = _walkin(client, auth_headers, [other["id"]], sport=sport)
    assert _admin_row(client, auth_headers, r2.json()["bookingRef"])["depositAmount"] is None


def test_amount_above_the_total_or_not_positive_is_rejected_and_books_nothing(client, auth_headers):
    sport, slot = _priced_slot(client, auth_headers)
    over = _walkin(client, auth_headers, [slot["id"]], sport=sport, amountPaid=slot["finalPrice"] + 1)
    assert over.status_code == 422 and over.json()["code"] == "amount_exceeds_total"
    assert _walkin(client, auth_headers, [slot["id"]], sport=sport, amountPaid=0).status_code == 422
    assert _walkin(client, auth_headers, [slot["id"]], sport=sport, amountPaid=-5).status_code == 422
    assert any(s["id"] == slot["id"] for s in _slots(client, auth_headers, sport=sport))  # slot still free


def test_amount_is_checked_against_the_total_after_the_promo(client, auth_headers):
    sport, slot = _priced_slot(client, auth_headers)
    # WELCOME10 takes 10% off: paying the pre-promo price must now be too much
    r = _walkin(client, auth_headers, [slot["id"]], sport=sport, promoCode="WELCOME10", amountPaid=slot["finalPrice"])
    assert r.status_code == 422 and r.json()["code"] == "amount_exceeds_total"


def test_balance_is_collected_later_in_parts_until_settled(client, auth_headers):
    r, slot = _advance_walkin(client, auth_headers, 100)
    b = r.json()
    row = _admin_row(client, auth_headers, b["bookingRef"])
    due = b["balanceDue"]
    first = client.post(f"/api/v1/admin/bookings/{row['id']}/collect-balance", json={"mode": "cash", "amount": 50}, headers=auth_headers)
    assert first.status_code == 200 and first.json()["balanceDue"] == round(due - 50, 2)
    too_much = client.post(f"/api/v1/admin/bookings/{row['id']}/collect-balance", json={"mode": "cash", "amount": due}, headers=auth_headers)
    assert too_much.status_code == 422
    rest = client.post(f"/api/v1/admin/bookings/{row['id']}/collect-balance", json={"mode": "upi"}, headers=auth_headers)
    assert rest.status_code == 200 and rest.json()["balanceDue"] == 0.0


def test_audit_records_what_was_paid_and_what_is_left(client, auth_headers):
    r, _ = _advance_walkin(client, auth_headers, 100)
    items, _total = deps.audit_repo.query(limit=200)
    row = next(x for x in items if x.action == "booking.walkin_create")
    assert "100" in str(row.detail) and "balanceDue" in str(row.detail)


# ── balance filter ──────────────────────────────────────────────────────────

def _listed(client, auth_headers, qs=""):
    return client.get(f"/api/v1/admin/bookings?limit=100&{qs}", headers=auth_headers).json()


def test_balance_filter_lists_only_bookings_with_money_still_to_collect(client, auth_headers):
    sport, slots_ = _priced_slot(client, auth_headers)
    free = [s for s in _slots(client, auth_headers, sport=sport) if s["finalPrice"]]
    assert len(free) >= 3
    owing = _walkin(client, auth_headers, [free[0]["id"]], sport=sport, amountPaid=100).json()
    settled = _walkin(client, auth_headers, [free[1]["id"]], sport=sport, amountPaid=100).json()
    full = _walkin(client, auth_headers, [free[2]["id"]], sport=sport).json()
    sid = _admin_row(client, auth_headers, settled["bookingRef"])["id"]
    client.post(f"/api/v1/admin/bookings/{sid}/collect-balance", json={"mode": "cash"}, headers=auth_headers)

    refs = [x["bookingRef"] for x in _listed(client, auth_headers, "balance=due")["items"]]
    assert refs == [owing["bookingRef"]]
    assert settled["bookingRef"] not in refs and full["bookingRef"] not in refs
    assert _listed(client, auth_headers, "balance=due")["total"] == 1


def test_balance_filter_drops_cancelled_and_still_lists_completed(client, auth_headers):
    sport, _slot = _priced_slot(client, auth_headers)
    free = [s for s in _slots(client, auth_headers, sport=sport) if s["finalPrice"]]
    a = _walkin(client, auth_headers, [free[0]["id"]], sport=sport, amountPaid=100).json()
    b = _walkin(client, auth_headers, [free[1]["id"]], sport=sport, amountPaid=100).json()
    client.patch(f"/api/v1/admin/bookings/{a['id']}", json={"status": "cancelled"}, headers=auth_headers)
    client.patch(f"/api/v1/admin/bookings/{b['id']}", json={"status": "completed"}, headers=auth_headers)
    refs = [x["bookingRef"] for x in _listed(client, auth_headers, "balance=due")["items"]]
    assert refs == [b["bookingRef"]]  # completed with a balance is still owed; and can still be collected
    done = client.post(f"/api/v1/admin/bookings/{b['id']}/collect-balance", json={"mode": "cash"}, headers=auth_headers)
    assert done.status_code == 200
    assert _listed(client, auth_headers, "balance=due")["total"] == 0


def test_balance_filter_rejects_other_values_and_applies_to_the_export(client, auth_headers):
    assert client.get("/api/v1/admin/bookings?balance=zzz", headers=auth_headers).status_code == 422
    sport, _s = _priced_slot(client, auth_headers)
    free = [s for s in _slots(client, auth_headers, sport=sport) if s["finalPrice"]]
    owing = _walkin(client, auth_headers, [free[0]["id"]], sport=sport, amountPaid=100).json()
    _walkin(client, auth_headers, [free[1]["id"]], sport=sport)  # fully paid
    text = client.get("/api/v1/admin/bookings/export?balance=due", headers=auth_headers).text
    assert owing["bookingRef"] in text and text.count("counter") == 1
    assert client.get("/api/v1/admin/bookings/export?balance=zzz", headers=auth_headers).status_code == 422
