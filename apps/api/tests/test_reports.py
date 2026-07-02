"""
Owner visibility (Detailed-Roadmap.md Phase 4). Covers: dashboard figures
(bookings today, café revenue today, occupancy) computed against seeded data,
Z-report (day-close) mode totals summing to the day's payments, and the
venue-timezone day boundary (the "today computed in browser/server local
time" bug noted in Roadmap.md) landing on the correct IST calendar day.

order_repo/invoice_repo/payment_repo are NOT reset between tests (see
conftest._reset_repos) — they're shared across the whole test session. Café
revenue assertions therefore use deltas or an isolated far-past date bucket
rather than absolute "today" totals, so they can't be polluted by other
tests' invoices/payments issued "now".
"""
import uuid
from datetime import date as date_cls, datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient

from main import app
from auth import hash_password, create_access_token, create_cashier_token
from db import _session
from db_models import PaymentRow
from models import BookingRecord, UserRecord
from services.availability_service import generate_slots
from services.venue_tz import get_venue_zoneinfo, local_today
import deps

client = TestClient(app)

ADMIN_HEADERS = {"Authorization": "Bearer " + create_access_token("admin", "admin")}


def _cashier_headers():
    uname = f"cashier_{uuid.uuid4().hex[:6]}"
    deps.user_repo.create(UserRecord(
        id=str(uuid.uuid4()), username=uname,
        hashed_password=hash_password("1234"), role="cashier",
        createdAt=datetime.now(timezone.utc).isoformat(), createdBy="admin",
    ))
    token = create_cashier_token(uname, "cashier")
    return {"Authorization": f"Bearer {token}"}


def _create_category():
    r = client.post(
        "/api/v1/admin/cafe/categories",
        json={"name": f"Cat-{uuid.uuid4().hex[:6]}", "kind": "food"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 201
    return r.json()["id"]


def _create_item(category_id: str, price: float, tax_rate: float, name: str):
    r = client.post(
        "/api/v1/admin/cafe/items",
        json={"category_id": category_id, "name": name, "price": price, "taxRatePercent": tax_rate},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 201
    return r.json()


def _create_order_with_items(cashier_headers, items: list[dict]):
    r = client.post("/api/v1/cafe/orders", json={"orderType": "quick", "items": items}, headers=cashier_headers)
    assert r.status_code == 201
    return r.json()


def _issue_invoice(order_id: str, cashier_headers):
    r = client.post(f"/api/v1/cafe/orders/{order_id}/invoice", json={}, headers=cashier_headers)
    assert r.status_code == 201
    return r.json()


def _add_payment(order_id: str, mode: str, amount: float, cashier_headers):
    r = client.post(f"/api/v1/cafe/orders/{order_id}/payments", json={"mode": mode, "amount": amount}, headers=cashier_headers)
    assert r.status_code == 201
    return r.json()


def _set_payment_created_at(payment_id: str, created_at_iso: str):
    with _session() as s:
        row = s.get(PaymentRow, payment_id)
        row.createdAt = created_at_iso


def _make_booking(date: str, slot, price: float, status: str):
    record = BookingRecord(
        id=str(uuid.uuid4()),
        bookingRef=str(uuid.uuid4())[:8].upper(),
        court_id=slot.courtId,
        slotId=slot.id,
        name="Reports Test",
        contact="9999900000",
        sportSlug=slot.sportSlug,
        date=date,
        startTime=slot.startTime,
        endTime=slot.endTime,
        party_size=1,
        price=price,
        status=status,
        createdAt=datetime.now(timezone.utc).isoformat(),
        is_primary=True,
        paymentStatus="paid" if status == "confirmed" else "unpaid",
    )
    return deps.booking_repo.create(record)


# ── Dashboard: bookings ─────────────────────────────────────────────────────

def test_dashboard_counts_confirmed_bookings_today_only():
    tz = get_venue_zoneinfo()
    today = local_today(tz)
    slots = generate_slots(date=today, drop_past=False)
    assert slots, "seed data must produce at least one slot today"

    _make_booking(today, slots[0], price=1200.0, status="confirmed")
    other = [s for s in slots if s.id != slots[0].id]
    if other:
        _make_booking(today, other[0], price=500.0, status="pending")  # must not count

    body = client.get("/api/v1/admin/reports/dashboard", headers=ADMIN_HEADERS).json()
    assert body["date"] == today
    assert body["bookingsToday"] == 1
    assert body["bookingRevenueToday"] == pytest.approx(1200.0)


def test_dashboard_ignores_bookings_on_other_dates():
    tz = get_venue_zoneinfo()
    today = local_today(tz)
    tomorrow = (date_cls.fromisoformat(today) + timedelta(days=1)).isoformat()
    tomorrow_slots = generate_slots(date=tomorrow, drop_past=False)
    assert tomorrow_slots
    _make_booking(tomorrow, tomorrow_slots[0], price=999.0, status="confirmed")

    body = client.get("/api/v1/admin/reports/dashboard", headers=ADMIN_HEADERS).json()
    assert body["bookingsToday"] == 0
    assert body["bookingRevenueToday"] == pytest.approx(0.0)


def test_dashboard_occupancy_ratio_against_total_bookable_slots():
    tz = get_venue_zoneinfo()
    today = local_today(tz)
    slots = generate_slots(date=today, drop_past=False)
    total = len(slots)
    assert total > 0
    _make_booking(today, slots[0], price=1200.0, status="confirmed")

    body = client.get("/api/v1/admin/reports/dashboard", headers=ADMIN_HEADERS).json()
    assert body["occupancyToday"] == pytest.approx(1 / total, rel=1e-3)


def test_dashboard_occupancy_zero_when_no_bookings():
    body = client.get("/api/v1/admin/reports/dashboard", headers=ADMIN_HEADERS).json()
    assert body["occupancyToday"] == 0.0


def test_dashboard_cafe_revenue_reflects_issued_invoices():
    before = client.get("/api/v1/admin/reports/dashboard", headers=ADMIN_HEADERS).json()

    cashier_headers = _cashier_headers()
    cat = _create_category()
    item = _create_item(cat, price=100.0, tax_rate=5.0, name="Reports Snack")
    order = _create_order_with_items(cashier_headers, [{"menu_item_id": item["id"], "qty": 1}])
    invoice = _issue_invoice(order["id"], cashier_headers)

    after = client.get("/api/v1/admin/reports/dashboard", headers=ADMIN_HEADERS).json()
    assert after["cafeRevenueToday"] - before["cafeRevenueToday"] == pytest.approx(invoice["total"])


def test_dashboard_requires_admin_auth():
    r = client.get("/api/v1/admin/reports/dashboard")
    assert r.status_code in (401, 403)


# ── Day-close (Z-report) ─────────────────────────────────────────────────────

def test_day_close_sums_by_payment_mode():
    cashier_headers = _cashier_headers()
    cat = _create_category()
    item = _create_item(cat, price=200.0, tax_rate=5.0, name="Zreport Item")

    order1 = _create_order_with_items(cashier_headers, [{"menu_item_id": item["id"], "qty": 1}])
    pay1 = _add_payment(order1["id"], "cash", 100.0, cashier_headers)
    order2 = _create_order_with_items(cashier_headers, [{"menu_item_id": item["id"], "qty": 1}])
    pay2 = _add_payment(order2["id"], "upi", 110.0, cashier_headers)

    target_date = "2020-06-15"  # isolated bucket — no other test dates payments here
    _set_payment_created_at(pay1["id"], f"{target_date}T10:00:00+00:00")
    _set_payment_created_at(pay2["id"], f"{target_date}T11:00:00+00:00")

    body = client.get(f"/api/v1/admin/reports/day-close?date={target_date}", headers=ADMIN_HEADERS).json()
    assert body["date"] == target_date
    assert body["totalTransactions"] == 2
    assert body["totalRevenue"] == pytest.approx(210.0)
    by_mode = {m["mode"]: m for m in body["byMode"]}
    assert by_mode["cash"]["total"] == pytest.approx(100.0)
    assert by_mode["cash"]["count"] == 1
    assert by_mode["upi"]["total"] == pytest.approx(110.0)
    assert by_mode["upi"]["count"] == 1


def test_day_close_defaults_to_venue_local_today():
    tz = get_venue_zoneinfo()
    body = client.get("/api/v1/admin/reports/day-close", headers=ADMIN_HEADERS).json()
    assert body["date"] == local_today(tz)


def test_day_close_empty_day_is_zero_not_error():
    body = client.get("/api/v1/admin/reports/day-close?date=2019-01-01", headers=ADMIN_HEADERS).json()
    assert body["totalRevenue"] == 0.0
    assert body["totalTransactions"] == 0
    assert body["byMode"] == []


def test_day_close_ist_midnight_boundary():
    """IST = UTC+5:30. A payment at 18:29:59 UTC on day D is still 23:59:59 IST
    on day D; at 18:30:00 UTC it has rolled to 00:00:00 IST on day D+1. This is
    the exact bug Roadmap.md flags (dashboard 'today' in the wrong timezone) —
    verify the half-open UTC boundary lands on the correct IST calendar day."""
    cashier_headers = _cashier_headers()
    cat = _create_category()
    item = _create_item(cat, price=50.0, tax_rate=5.0, name="Boundary Item")

    order_a = _create_order_with_items(cashier_headers, [{"menu_item_id": item["id"], "qty": 1}])
    pay_a = _add_payment(order_a["id"], "cash", 42.0, cashier_headers)
    _set_payment_created_at(pay_a["id"], "2020-06-20T18:29:59+00:00")  # 23:59:59 IST on the 20th

    order_b = _create_order_with_items(cashier_headers, [{"menu_item_id": item["id"], "qty": 1}])
    pay_b = _add_payment(order_b["id"], "cash", 77.0, cashier_headers)
    _set_payment_created_at(pay_b["id"], "2020-06-20T18:30:00+00:00")  # 00:00:00 IST on the 21st

    day20 = client.get("/api/v1/admin/reports/day-close?date=2020-06-20", headers=ADMIN_HEADERS).json()
    day21 = client.get("/api/v1/admin/reports/day-close?date=2020-06-21", headers=ADMIN_HEADERS).json()

    assert day20["totalRevenue"] == pytest.approx(42.0)
    assert day21["totalRevenue"] == pytest.approx(77.0)


def test_day_close_requires_admin_auth():
    r = client.get("/api/v1/admin/reports/day-close")
    assert r.status_code in (401, 403)
