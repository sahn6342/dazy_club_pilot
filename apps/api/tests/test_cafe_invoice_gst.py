"""
Café GST correctness (Detailed-Roadmap.md Phase 2).
Covers: mixed-rate invoices compute correct per-line CGST/SGST, invoice
numbering stays gap-free even when issuance fails mid-transaction, and
the printable receipt shows FSSAI + a rate-wise GST summary and switches
title between Tax Invoice / Bill of Supply by scheme.
"""
import uuid
from datetime import datetime, timezone

import pytest
from starlette.testclient import TestClient

from main import app
from auth import hash_password, create_access_token, create_cashier_token
from db import _session
from db_models import InvoiceSequenceRow
from models import UserRecord
from repositories.invoice_repo import SqliteInvoiceRepository
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
        json={
            "category_id": category_id, "name": name, "price": price,
            "taxRatePercent": tax_rate,
        },
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 201
    return r.json()


def _create_order_with_items(cashier_headers, items: list[dict]):
    """items: list of {"menu_item_id": id, "qty": n}."""
    r = client.post(
        "/api/v1/cafe/orders",
        json={"orderType": "quick", "items": items},
        headers=cashier_headers,
    )
    assert r.status_code == 201
    return r.json()


def _issue_invoice(order_id: str, cashier_headers):
    r = client.post(f"/api/v1/cafe/orders/{order_id}/invoice", json={}, headers=cashier_headers)
    assert r.status_code == 201
    return r.json()


# ── Mixed-rate GST correctness ─────────────────────────────────────────────

def test_mixed_rate_invoice_correct_per_line_gst():
    cashier_headers = _cashier_headers()
    cat = _create_category()
    item_5pct = _create_item(cat, price=100.0, tax_rate=5.0, name="Snack")
    item_18pct = _create_item(cat, price=200.0, tax_rate=18.0, name="Packaged Drink")

    order = _create_order_with_items(cashier_headers, [
        {"menu_item_id": item_5pct["id"], "qty": 2},   # 200 subtotal, 5% -> 10 tax
        {"menu_item_id": item_18pct["id"], "qty": 1},  # 200 subtotal, 18% -> 36 tax
    ])

    invoice = _issue_invoice(order["id"], cashier_headers)

    lines_by_rate = {round(l["gstRatePercent"]): l for l in invoice["lines"]}
    assert 5 in lines_by_rate and 18 in lines_by_rate

    line5 = lines_by_rate[5]
    assert line5["taxableValue"] == pytest.approx(200.0)
    assert line5["cgst"] == pytest.approx(5.0)   # half of 10
    assert line5["sgst"] == pytest.approx(5.0)

    line18 = lines_by_rate[18]
    assert line18["taxableValue"] == pytest.approx(200.0)
    assert line18["cgst"] == pytest.approx(18.0)  # half of 36
    assert line18["sgst"] == pytest.approx(18.0)

    # Invoice-level totals are the SUM across both rates, not a single flat rate on the total.
    assert invoice["taxableValue"] == pytest.approx(400.0)
    assert invoice["cgst"] == pytest.approx(23.0)   # 5 + 18
    assert invoice["sgst"] == pytest.approx(23.0)
    # 400 taxable + 23 cgst + 23 sgst = 446, rounded to nearest rupee
    assert invoice["total"] == pytest.approx(446.0, abs=1.0)


# ── Invoice number atomicity ────────────────────────────────────────────────

def test_invoice_sequence_no_gap_on_mid_transaction_failure():
    """A crash after the sequence bump but before the transaction commits
    must roll back the bump too — otherwise the number is burned but no
    invoice was ever issued (a gap in the legally-required sequence)."""
    repo = SqliteInvoiceRepository()
    series, fy = "TESTSEQ", "9999"

    with pytest.raises(RuntimeError):
        with _session() as s:
            n = repo.next_number(series, fy, session=s)
            assert n == 1
            raise RuntimeError("simulated failure after sequence bump, before commit")

    # The aborted attempt must not have persisted the bump.
    with _session() as s:
        row = s.get(InvoiceSequenceRow, f"{series}-{fy}")
        assert row is None

    # A fresh, successful call gets 1 again — no gap, no leaked number.
    n2 = repo.next_number(series, fy)
    assert n2 == 1


def test_issue_invoice_end_to_end_still_works_after_atomicity_fix():
    """Sanity check that folding next_number into create()'s own session
    didn't break the normal (non-failing) path."""
    cashier_headers = _cashier_headers()
    cat = _create_category()
    item = _create_item(cat, price=50.0, tax_rate=5.0, name="Tea")
    order = _create_order_with_items(cashier_headers, [{"menu_item_id": item["id"], "qty": 1}])
    invoice = _issue_invoice(order["id"], cashier_headers)
    assert invoice["invoiceNo"]
    assert invoice["status"] == "issued"


# ── Printable receipt: FSSAI, rate-wise summary, title switch ──────────────

def test_print_shows_fssai_rate_summary_and_tax_invoice_title():
    cashier_headers = _cashier_headers()
    r = client.put(
        "/api/v1/admin/cafe/settings",
        json={"legalName": "Dazy Café", "gstin": "29ABCDE1234F1Z5", "fssaiNumber": "12345678901234", "scheme": "regular"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    try:
        cat = _create_category()
        item_5pct = _create_item(cat, price=100.0, tax_rate=5.0, name="Snack")
        item_18pct = _create_item(cat, price=200.0, tax_rate=18.0, name="Packaged Drink")
        order = _create_order_with_items(cashier_headers, [
            {"menu_item_id": item_5pct["id"], "qty": 1},
            {"menu_item_id": item_18pct["id"], "qty": 1},
        ])
        invoice = _issue_invoice(order["id"], cashier_headers)

        r = client.get(f"/api/v1/cafe/invoices/{invoice['id']}/print")
        assert r.status_code == 200
        html = r.text
        assert "FSSAI: 12345678901234" in html
        assert "TAX INVOICE" in html
        assert "GST 5%" in html
        assert "GST 18%" in html
    finally:
        # Note: PUT /admin/cafe/settings drops None values (can't un-set gstin this way),
        # but scheme="unregistered" alone is sufficient to force bill_of_supply afterward
        # regardless of the leftover gstin — see invoice_repo.create's `or not gstin` check.
        client.put("/api/v1/admin/cafe/settings", json={"scheme": "regular"}, headers=ADMIN_HEADERS)


def test_print_shows_bill_of_supply_when_unregistered():
    cashier_headers = _cashier_headers()
    r = client.put(
        "/api/v1/admin/cafe/settings",
        json={"scheme": "unregistered", "gstin": None},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    try:
        cat = _create_category()
        item = _create_item(cat, price=50.0, tax_rate=5.0, name="Coffee")
        order = _create_order_with_items(cashier_headers, [{"menu_item_id": item["id"], "qty": 1}])
        invoice = _issue_invoice(order["id"], cashier_headers)
        assert invoice["invoiceType"] == "bill_of_supply"

        r = client.get(f"/api/v1/cafe/invoices/{invoice['id']}/print")
        assert r.status_code == 200
        assert "BILL OF SUPPLY" in r.text
    finally:
        client.put("/api/v1/admin/cafe/settings", json={"scheme": "regular"}, headers=ADMIN_HEADERS)
