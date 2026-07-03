"""
Café x turf synergy, sub-step 1 (Detailed-Roadmap.md Phase 7): a customer can
attach a café pre-order to their own confirmed booking. Covers: public menu
read (no inventory internals leaked), identity check via contact match,
confirmed-only gate, order creation with correct totals + booking_id link,
and staff visibility via the existing cashier order endpoints.
"""
import uuid

import pytest
from starlette.testclient import TestClient

from main import app
from auth import create_access_token

client = TestClient(app)

ADMIN_HEADERS = {"Authorization": "Bearer " + create_access_token("admin", "admin")}


def _create_free_promo() -> str:
    code = f"FREE{uuid.uuid4().hex[:6].upper()}"
    r = client.post(
        "/api/v1/admin/promos",
        json={"code": code, "kind": "percent", "value": 100, "active": True,
              "valid_from": None, "valid_to": None, "max_uses": None, "sport_slug": None},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 201
    return code


def _book_confirmed(contact="9812345670"):
    r = client.get("/api/v1/slots?sport=badminton")
    slot = next(s for s in r.json() if s["available"])
    promo = _create_free_promo()
    body = {
        "name": "Preorder Test", "contact": contact, "sportSlug": slot["sportSlug"],
        "date": slot["date"], "startTime": slot["startTime"], "slotIds": [slot["id"]],
        "players": 1, "promoCode": promo,
    }
    r = client.post("/api/v1/bookings", json=body)
    assert r.status_code == 201
    booking = r.json()
    assert booking["status"] == "confirmed"
    return booking


def _menu_item(price=100.0, tax=5.0):
    cat = client.post("/api/v1/admin/cafe/categories", json={"name": f"Cat-{uuid.uuid4().hex[:6]}", "kind": "food"}, headers=ADMIN_HEADERS).json()
    item = client.post(
        "/api/v1/admin/cafe/items",
        json={"category_id": cat["id"], "name": "Preorder Snack", "price": price, "taxRatePercent": tax},
        headers=ADMIN_HEADERS,
    ).json()
    return item


# ── Public menu ──────────────────────────────────────────────────────────────

def test_public_menu_lists_available_items_without_inventory_internals():
    item = _menu_item()
    r = client.get("/api/v1/menu")
    assert r.status_code == 200
    body = r.json()
    found = next(i for i in body["items"] if i["id"] == item["id"])
    assert found["price"] == pytest.approx(100.0)
    assert "currentQty" not in found
    assert "reorderLevel" not in found
    assert "trackInventory" not in found
    assert "purchaseCost" not in found


def test_public_menu_requires_no_auth():
    r = client.get("/api/v1/menu")
    assert r.status_code == 200


# ── Pre-order creation ───────────────────────────────────────────────────────

def test_preorder_creates_order_linked_to_booking():
    booking = _book_confirmed(contact="9812345670")
    item = _menu_item(price=100.0, tax=5.0)

    r = client.post(
        f"/api/v1/bookings/{booking['bookingRef']}/preorder",
        json={"contact": "9812345670", "items": [{"menu_item_id": item["id"], "qty": 2}]},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["orderNo"]
    assert body["items"] == [{"name": "Preorder Snack", "qty": 2, "lineTotal": pytest.approx(210.0)}]
    assert body["total"] == pytest.approx(210.0)

    # Staff-side: the order is visible via the normal cashier endpoint, linked to the booking.
    cashier_headers = _cashier_headers()
    orders = client.get("/api/v1/cafe/orders", headers=cashier_headers).json()
    linked = next(o for o in orders if o["orderNo"] == body["orderNo"])
    assert linked["orderType"] == "takeaway"


def _cashier_headers():
    from datetime import datetime, timezone
    from auth import hash_password, create_cashier_token
    from models import UserRecord
    import deps
    uname = f"cashier_{uuid.uuid4().hex[:6]}"
    deps.user_repo.create(UserRecord(
        id=str(uuid.uuid4()), username=uname,
        hashed_password=hash_password("1234"), role="cashier",
        createdAt=datetime.now(timezone.utc).isoformat(), createdBy="admin",
    ))
    token = create_cashier_token(uname, "cashier")
    return {"Authorization": f"Bearer {token}"}


def test_preorder_wrong_contact_returns_404():
    booking = _book_confirmed(contact="9812345670")
    item = _menu_item()
    r = client.post(
        f"/api/v1/bookings/{booking['bookingRef']}/preorder",
        json={"contact": "9999999999", "items": [{"menu_item_id": item["id"], "qty": 1}]},
    )
    assert r.status_code == 404


def test_preorder_unknown_booking_ref_returns_404():
    item = _menu_item()
    r = client.post(
        "/api/v1/bookings/NOSUCHREF/preorder",
        json={"contact": "9812345670", "items": [{"menu_item_id": item["id"], "qty": 1}]},
    )
    assert r.status_code == 404


def test_preorder_rejects_unconfirmed_booking():
    r = client.get("/api/v1/slots?sport=cricket")
    slot = next(s for s in r.json() if s["available"])
    body = {
        "name": "Pending Test", "contact": "9812345671", "sportSlug": slot["sportSlug"],
        "date": slot["date"], "startTime": slot["startTime"], "slotIds": [slot["id"]], "players": 1,
    }
    booking = client.post("/api/v1/bookings", json=body).json()
    assert booking["status"] == "pending"

    item = _menu_item()
    r = client.post(
        f"/api/v1/bookings/{booking['bookingRef']}/preorder",
        json={"contact": "9812345671", "items": [{"menu_item_id": item["id"], "qty": 1}]},
    )
    assert r.status_code == 400


def test_preorder_unknown_menu_item_returns_404():
    booking = _book_confirmed(contact="9812345672")
    r = client.post(
        f"/api/v1/bookings/{booking['bookingRef']}/preorder",
        json={"contact": "9812345672", "items": [{"menu_item_id": "nope", "qty": 1}]},
    )
    assert r.status_code == 404


def test_preorder_empty_items_rejected():
    booking = _book_confirmed(contact="9812345673")
    r = client.post(
        f"/api/v1/bookings/{booking['bookingRef']}/preorder",
        json={"contact": "9812345673", "items": []},
    )
    assert r.status_code == 422
