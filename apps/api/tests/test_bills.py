"""Counter bills: GST maths, gap-free numbering, immutability (void only), search, access control."""
from datetime import date, timedelta

import pytest

import deps
from repositories import bill_repo as bill_repo_module
from repositories.bill_repo import financial_year, financial_year_label
from services.billing import calc_bill

URL = "/api/v1/admin/bills"


def _line(description="Court hire", qty=1, rate=1000, gst=18):
    return {"description": description, "qty": qty, "rate": rate, "gstRatePercent": gst}


def _make(client, headers, lines=None, **extra):
    r = client.post(URL, json={"lines": lines or [_line()], **extra}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# ── maths ───────────────────────────────────────────────────────────────────

def test_price_includes_gst_which_is_backed_out_and_split_equally():
    t = calc_bill([("A", 2, 100.50, 18), ("B", 1, 50, 5), ("C", 3, 33.33, 12)])
    assert [str(x.line_total) for x in t.lines] == ["201.00", "50.00", "99.99"]  # qty x rate, exactly as typed
    assert [str(x.taxable) for x in t.lines] == ["170.34", "47.62", "89.29"]
    assert [str(x.cgst) for x in t.lines] == ["15.33", "1.19", "5.35"]
    assert all(x.cgst == x.sgst for x in t.lines)
    assert all(x.taxable + x.cgst + x.sgst == x.line_total for x in t.lines)
    assert str(t.taxable) == "307.25" and str(t.cgst) == "21.87" and str(t.sgst) == "21.87"
    assert str(t.round_off) == "0.00" and str(t.total) == "350.99"  # not rounded to the rupee


def test_zero_rated_line_has_no_tax():
    t = calc_bill([("Water", 4, 20, 0)])
    assert str(t.taxable) == "80.00" and str(t.cgst) == "0.00" and str(t.sgst) == "0.00" and str(t.total) == "80.00"


def test_odd_paisa_of_tax_stays_in_the_taxable_value_so_cgst_equals_sgst():
    t = calc_bill([("A", 1, 1.05, 5)])  # tax 0.05 cannot be halved to whole paise
    line = t.lines[0]
    assert str(line.cgst) == "0.02" and str(line.sgst) == "0.02" and str(line.taxable) == "1.01"
    assert str(t.total) == "1.05"


def test_fractional_tax_percentage():
    t = calc_bill([("A", 1, 1000, 2.5)])
    line = t.lines[0]
    assert str(line.cgst) == "12.19" and str(line.taxable) == "975.62" and str(t.total) == "1000.00"


def test_server_ignores_any_client_total(client, auth_headers):
    r = client.post(URL, json={"lines": [_line(rate=1000, gst=18)], "total": 1, "cgst": 0}, headers=auth_headers)
    assert r.status_code == 201
    b = r.json()
    assert b["total"] == 1000.0 and b["cgst"] == 76.27 and b["sgst"] == 76.27 and b["taxableValue"] == 847.46


def test_created_bill_has_lines_words_and_status(client, auth_headers):
    b = _make(client, auth_headers, [_line("Hall", 1, 1000, 18), _line("Tea", 2, 25, 5)],
              customerName="Asha", customerPhone="9876501234", notes="Birthday")
    assert b["status"] == "active" and b["customerName"] == "Asha" and b["notes"] == "Birthday"
    assert [ln["description"] for ln in b["lines"]] == ["Hall", "Tea"]
    assert b["taxableValue"] == 895.08 and b["cgst"] == 77.46 and b["sgst"] == 77.46
    assert b["roundOff"] == 0 and b["total"] == 1050.0
    assert b["amountInWords"] == "One Thousand Fifty Rupees Only"


def test_new_bills_are_tax_inclusive_and_old_ones_keep_their_meaning(client, auth_headers):
    from db import _session
    from db_models import BillRow
    new = _make(client, auth_headers)
    old = _make(client, auth_headers)
    with _session() as s:  # a bill issued before prices included GST
        s.get(BillRow, old["id"]).prices_include_tax = False
    assert client.get(f"{URL}/{new['id']}", headers=auth_headers).json()["pricesIncludeTax"] is True
    assert client.get(f"{URL}/{old['id']}", headers=auth_headers).json()["pricesIncludeTax"] is False


# ── numbering ───────────────────────────────────────────────────────────────

def test_numbers_are_sequential_in_the_financial_year_series(client, auth_headers):
    first, second = _make(client, auth_headers), _make(client, auth_headers)
    label = financial_year_label(first["billDate"])
    assert first["billNo"] == f"{label}/0001" and second["billNo"] == f"{label}/0002"


def test_bill_number_shows_the_financial_year_as_start_year_dash_end_year():
    assert financial_year_label("2026-03-31") == "2025-26" and financial_year_label("2026-04-01") == "2026-27"
    assert financial_year_label("2099-12-31") == "2099-00"  # century rollover: last two digits of the end year


def test_financial_year_starts_in_april():
    assert financial_year("2026-03-31") == "2526" and financial_year("2026-04-01") == "2627"
    assert financial_year("2026-12-31") == "2627" and financial_year("2027-01-01") == "2627"
    assert financial_year("2099-12-31") == "9900"


def test_a_failed_bill_does_not_burn_a_number(client, auth_headers, monkeypatch):
    totals = calc_bill([("A", 1, 100, 18)])
    kwargs = dict(local_date="2026-10-28", totals=totals, customer_name=None, customer_phone=None,
                  customer_gstin=None, notes=None, booking_ref=None, created_by="admin")

    def boom(_):
        raise RuntimeError("insert failed")

    monkeypatch.setattr(bill_repo_module, "amount_in_words", boom)
    with pytest.raises(RuntimeError):
        deps.bill_repo.create(**kwargs)
    monkeypatch.undo()
    assert deps.bill_repo.create(**kwargs)["billNo"] == "2026-27/0001"


def test_sequence_restarts_for_a_new_financial_year():
    totals = calc_bill([("A", 1, 100, 18)])
    kw = dict(totals=totals, customer_name=None, customer_phone=None, customer_gstin=None, notes=None,
              booking_ref=None, created_by="admin")
    assert deps.bill_repo.create(local_date="2027-03-31", **kw)["billNo"] == "2026-27/0001"
    assert deps.bill_repo.create(local_date="2027-04-01", **kw)["billNo"] == "2027-28/0001"
    assert deps.bill_repo.create(local_date="2027-04-02", **kw)["billNo"] == "2027-28/0002"


# ── retrieve, search, void ──────────────────────────────────────────────────

def test_old_bill_can_be_fetched_with_its_lines(client, auth_headers):
    made = _make(client, auth_headers, [_line("A"), _line("B", 2, 10, 5)])
    got = client.get(f"{URL}/{made['id']}", headers=auth_headers).json()
    assert got == made
    assert client.get(f"{URL}/nope", headers=auth_headers).status_code == 404


def test_list_is_newest_first_and_searchable(client, auth_headers):
    a = _make(client, auth_headers, customerName="Meena Rao", customerPhone="9000000001")
    b = _make(client, auth_headers, customerName="Karan", customerPhone="9000000002")
    items = client.get(URL, headers=auth_headers).json()
    assert [x["billNo"] for x in items["items"]] == [b["billNo"], a["billNo"]] and items["total"] == 2
    assert "lines" not in items["items"][0]
    for q, want in (("meena", a), ("9000000002", b), (a["billNo"], a), ("0002", b)):
        got = client.get(f"{URL}?q={q}", headers=auth_headers).json()["items"]
        assert [x["id"] for x in got] == [want["id"]], q
    assert client.get(f"{URL}?q=%25", headers=auth_headers).json()["total"] == 0  # a literal %, not a wildcard


def test_list_filters_by_date_and_status_and_pages(client, auth_headers):
    made = [_make(client, auth_headers) for _ in range(3)]
    today = made[0]["billDate"]
    tomorrow = (date.fromisoformat(today) + timedelta(days=1)).isoformat()
    assert client.get(f"{URL}?date_from={tomorrow}", headers=auth_headers).json()["total"] == 0
    assert client.get(f"{URL}?date_from={today}&date_to={today}", headers=auth_headers).json()["total"] == 3
    page = client.get(f"{URL}?limit=2&offset=2", headers=auth_headers).json()
    assert page["total"] == 3 and len(page["items"]) == 1
    client.post(f"{URL}/{made[0]['id']}/void", json={"reason": "Wrong item"}, headers=auth_headers)
    assert client.get(f"{URL}?status=void", headers=auth_headers).json()["total"] == 1
    assert client.get(f"{URL}?status=active", headers=auth_headers).json()["total"] == 2
    assert client.get(f"{URL}?status=bogus", headers=auth_headers).status_code == 422


def test_void_keeps_the_number_and_cannot_repeat(client, auth_headers):
    b = _make(client, auth_headers)
    r = client.post(f"{URL}/{b['id']}/void", json={"reason": "Customer left"}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["status"] == "void" and r.json()["voidReason"] == "Customer left"
    assert r.json()["voidedBy"] and r.json()["billNo"] == b["billNo"]
    assert client.post(f"{URL}/{b['id']}/void", json={"reason": "again"}, headers=auth_headers).status_code == 409
    assert _make(client, auth_headers)["billNo"].endswith("/0002")  # a void number is never reused
    assert client.post(f"{URL}/nope/void", json={"reason": "xyz"}, headers=auth_headers).status_code == 404
    assert client.post(f"{URL}/{b['id']}/void", json={"reason": "x"}, headers=auth_headers).status_code == 422


def test_there_is_no_way_to_edit_or_delete_a_bill(client, auth_headers):
    b = _make(client, auth_headers)
    assert client.put(f"{URL}/{b['id']}", json={}, headers=auth_headers).status_code in (404, 405)
    assert client.patch(f"{URL}/{b['id']}", json={}, headers=auth_headers).status_code in (404, 405)
    assert client.delete(f"{URL}/{b['id']}", headers=auth_headers).status_code in (404, 405)


# ── validation ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("payload", [
    {"lines": []},
    {"lines": [{"description": "", "qty": 1, "rate": 10, "gstRatePercent": 5}]},
    {"lines": [{"description": "  ", "qty": 1, "rate": 10, "gstRatePercent": 5}]},
    {"lines": [{"description": "x", "qty": 0, "rate": 10, "gstRatePercent": 5}]},
    {"lines": [{"description": "x", "qty": 1, "rate": -1, "gstRatePercent": 5}]},
    {"lines": [{"description": "x", "qty": 1, "rate": 10, "gstRatePercent": 40}]},
    {"lines": [{"description": "x", "qty": 1, "rate": 10, "gstRatePercent": 5}], "customerPhone": "123"},
    {"lines": [{"description": "x", "qty": 1, "rate": 10, "gstRatePercent": 5}], "customerGstin": "BADGSTIN"},
    {"lines": [{"description": "x", "qty": 1, "rate": 0, "gstRatePercent": 5}]},  # total 0
])
def test_bad_bills_are_rejected_and_use_no_number(client, auth_headers, payload):
    assert client.post(URL, json=payload, headers=auth_headers).status_code == 422
    assert _make(client, auth_headers)["billNo"].endswith("/0001")


def test_valid_customer_gstin_is_kept_uppercase(client, auth_headers):
    b = _make(client, auth_headers, customerGstin="10abcde1234f1z5")
    assert b["customerGstin"] == "10ABCDE1234F1Z5"


def test_blank_optional_fields_become_null(client, auth_headers):
    b = _make(client, auth_headers, customerName="  ", customerPhone="", notes="", customerGstin="")
    assert b["customerName"] is None and b["customerPhone"] is None and b["notes"] is None and b["customerGstin"] is None


def test_too_many_lines_are_rejected(client, auth_headers):
    assert client.post(URL, json={"lines": [_line()] * 51}, headers=auth_headers).status_code == 422


def test_bill_can_link_to_an_existing_booking_only(client, auth_headers):
    assert client.post(URL, json={"lines": [_line()], "bookingRef": "NOSUCH00"}, headers=auth_headers).status_code == 404
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    slot = [s for s in client.get(f"/api/v1/slots?sport=cricket&date={tomorrow}").json() if s["available"]][0]
    ref = client.post("/api/v1/admin/bookings/walkin", headers=auth_headers, json={
        "name": "Ravi", "contact": "9123456780", "slotIds": [slot["id"]], "sportSlug": "cricket", "date": tomorrow,
        "players": 2, "paymentMode": "cash"}).json()["bookingRef"]
    assert _make(client, auth_headers, bookingRef=ref)["bookingRef"] == ref


# ── business header, access, audit ──────────────────────────────────────────

def test_business_header_comes_from_contact_details_and_is_not_shadowed_by_the_id_route(client, auth_headers):
    plain = client.get(f"{URL}/business", headers=auth_headers)
    assert plain.status_code == 200 and plain.json()["title"] == "Bill" and plain.json()["gstin"] is None
    for key, value in (("venue_name", "Dazy Sports"), ("venue_address", "D1, Danapur, Patna"),
                       ("venue_phone", "+91 90000 00000"), ("venue_email", "hello@dazy.test"),
                       ("venue_gstin", "10abcde1234f1z5")):
        r = client.put(f"/api/v1/admin/cms/{key}", json={"value": value}, headers=auth_headers)
        assert r.status_code == 200, (key, r.text)
    b = client.get(f"{URL}/business", headers=auth_headers).json()
    assert b == {"name": "Dazy Sports", "gstin": "10ABCDE1234F1Z5", "address": "D1, Danapur, Patna",
                 "phone": "+91 90000 00000", "email": "hello@dazy.test", "title": "Tax Invoice"}


def test_cafe_settings_no_longer_change_the_bill_header(client, auth_headers):
    client.put("/api/v1/admin/cafe/settings", headers=auth_headers, json={"legalName": "Café Only Name", "gstin": "29ABCDE1234F1Z5"})
    b = client.get(f"{URL}/business", headers=auth_headers).json()
    assert b["name"] != "Café Only Name" and b["gstin"] is None


def test_venue_gstin_is_empty_or_well_formed_and_never_public(client, auth_headers):
    assert any(e["key"] == "venue_gstin" for e in client.get("/api/v1/admin/cms", headers=auth_headers).json())
    for bad in ("123", "10ABCDE1234F1Z", "BADGSTIN12345Z5"):
        assert client.put("/api/v1/admin/cms/venue_gstin", json={"value": bad}, headers=auth_headers).status_code == 422, bad
    assert client.put("/api/v1/admin/cms/venue_gstin", json={"value": ""}, headers=auth_headers).status_code == 200
    client.put("/api/v1/admin/cms/venue_gstin", json={"value": "10ABCDE1234F1Z5"}, headers=auth_headers)
    assert all(e["key"] != "venue_gstin" for e in client.get("/api/v1/venue").json())


def test_every_bill_route_needs_an_admin(client):
    for method, path in (("get", URL), ("post", URL), ("get", f"{URL}/business"), ("get", f"{URL}/x"), ("post", f"{URL}/x/void")):
        assert getattr(client, method)(path).status_code in (401, 403), (method, path)


def test_create_and_void_are_audited(client, auth_headers):
    b = _make(client, auth_headers)
    client.post(f"{URL}/{b['id']}/void", json={"reason": "Test void"}, headers=auth_headers)
    items, _ = deps.audit_repo.query(limit=200)
    actions = [r.action for r in items]
    assert actions.count("bill.create") == 1 and actions.count("bill.void") == 1
    assert b["billNo"] in str([r.detail for r in items if r.action == "bill.create"])
