"""Workstream E: SQL-side pagination/filtering/sorting, streamed CSV export, soft delete."""
import csv
import io
import json
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import event, insert, text

import deps
from auth import create_cashier_token, hash_password
from db import _session, engine
from db_models import BookingRow, EnquiryRow, CustomerRow
from models import UserRecord

SPORTS = ["cricket", "badminton", "pickleball"]
STATUSES = ["pending", "confirmed", "completed", "cancelled", "no_show"]
N = 1500


@contextmanager
def count_statements(fragment: str):
    """Collect the SQL statements issued inside the block that mention `fragment`."""
    seen: list[str] = []

    def on_exec(conn, cursor, statement, parameters, context, executemany):
        if fragment in statement.lower():
            seen.append(statement)

    event.listen(engine, "before_cursor_execute", on_exec)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", on_exec)


def _seed_bookings(n=N):
    """n primary bookings (+ one secondary row each 10th) inserted in bulk, deterministic fields."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(n):
        d = (date(2026, 11, 1) + timedelta(days=i % 30)).isoformat()
        rows.append(dict(
            id=f"seed-{i:05d}", bookingRef=f"SEED{i:05d}", customer_id=None, court_id="court-cricket",
            slotId=f"seed-slot-{i}", name=("alice " if i % 2 else "Bob ") + str(i), contact=f"9{i:09d}",
            contact_norm=f"9{i:09d}", sportSlug=SPORTS[i % 3], date=d, startTime="06:00", endTime="07:00",
            party_size=1, price=None if i % 7 == 0 else float(100 + (i % 50)), status=STATUSES[i % 5],
            createdAt=(base + timedelta(minutes=i)).isoformat(), is_primary=True,
            paymentStatus="unpaid", gst_rate_percent=18.0 if i % 7 else None,
        ))
        if i % 10 == 0:  # secondary slot rows must never be counted or listed
            rows.append({**rows[-1], "id": f"seed-{i:05d}-b", "slotId": f"seed-slot-{i}-b", "is_primary": False, "startTime": "07:00", "endTime": "08:00"})
    with _session() as s:
        s.execute(insert(BookingRow), rows)


@pytest.fixture
def seeded(client, auth_headers):
    _seed_bookings()
    return auth_headers


def _list(client, h, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    r = client.get(f"/api/v1/admin/bookings?{q}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


# ── listing ────────────────────────────────────────────────────────────────

def test_total_counts_primary_rows_only(client, seeded):
    assert _list(client, seeded, limit=1)["total"] == N


def test_paging_is_stable_and_complete(client, seeded):
    seen, offset = [], 0
    while True:
        page = _list(client, seeded, limit=100, offset=offset, sort_by="createdAt", sort_dir="asc")
        seen += [b["id"] for b in page["items"]]
        if len(page["items"]) < 100:
            break
        offset += 100
    assert len(seen) == N and len(set(seen)) == N  # no row skipped or repeated across pages
    assert seen == sorted(seen)  # createdAt asc == insertion order here


def test_limit_is_capped_and_offset_past_the_end_is_empty(client, seeded):
    assert len(_list(client, seeded, limit=5000)["items"]) == 100
    beyond = _list(client, seeded, limit=25, offset=N + 10)
    assert beyond["items"] == [] and beyond["total"] == N


def test_filters_combine_in_sql(client, seeded):
    page = _list(client, seeded, sport="cricket", status="confirmed", date_from="2026-11-05", date_to="2026-11-12", limit=100)
    assert page["total"] > 0
    assert all(b["sportSlug"] == "cricket" and b["status"] == "confirmed" and "2026-11-05" <= b["date"] <= "2026-11-12"
               for b in page["items"])
    expected = sum(1 for i in range(N) if SPORTS[i % 3] == "cricket" and STATUSES[i % 5] == "confirmed"
                   and "2026-11-05" <= (date(2026, 11, 1) + timedelta(days=i % 30)).isoformat() <= "2026-11-12")
    assert page["total"] == expected


@pytest.mark.parametrize("sort_by", ["date", "createdAt", "price", "name", "sportSlug", "status"])
@pytest.mark.parametrize("sort_dir", ["asc", "desc"])
def test_every_sort_column_orders_correctly(client, seeded, sort_by, sort_dir):
    items = _list(client, seeded, sort_by=sort_by, sort_dir=sort_dir, limit=100)["items"]
    key = {"name": lambda b: b["name"].lower(), "price": lambda b: (b["price"] is None, b["price"] or 0)}.get(sort_by, lambda b: b[sort_by])
    keys = [key(b) for b in items]
    assert keys == sorted(keys, reverse=(sort_dir == "desc"))


def test_unknown_sort_column_falls_back_to_date(client, seeded):
    dates = [b["date"] for b in _list(client, seeded, sort_by="DROP TABLE", sort_dir="desc", limit=50)["items"]]
    assert dates == sorted(dates, reverse=True)


def test_listing_runs_two_booking_queries_regardless_of_table_size(client, seeded):
    with count_statements("from bookings") as stmts:
        _list(client, seeded, limit=100, sort_by="name")
    assert len(stmts) == 2  # one COUNT, one page


def test_bad_deleted_mode_is_rejected(client, auth_headers):
    assert client.get("/api/v1/admin/bookings?deleted=maybe", headers=auth_headers).status_code == 422


# ── CSV export ─────────────────────────────────────────────────────────────

def _export(client, h, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return client.get(f"/api/v1/admin/bookings/export?{q}", headers=h)


def _rows(resp):
    text_ = resp.content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text_)))


def test_export_is_csv_with_every_matching_row_not_just_one_page(client, seeded):
    r = _export(client, seeded)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert 'attachment; filename="bookings-' in r.headers["content-disposition"]
    assert r.content.startswith(b"\xef\xbb\xbf")  # BOM for Excel
    rows = _rows(r)
    assert rows[0][:4] == ["Ref", "Name", "Contact", "Sport"] and len(rows) - 1 == N


def test_export_respects_filters_and_sort(client, seeded):
    rows = _rows(_export(client, seeded, sport="badminton", status="cancelled", sort_by="createdAt", sort_dir="asc"))[1:]
    assert rows and all(r[3] == "badminton" and r[12] == "cancelled" for r in rows)
    refs = [r[0] for r in rows]
    assert refs == sorted(refs)


def test_export_computes_gst_and_leaves_free_bookings_blank(client, seeded):
    rows = {r[0]: r for r in _rows(_export(client, seeded))[1:]}
    priced = rows["SEED00001"]  # i=1: price 101, 18% GST
    assert priced[8] == "101.0" and priced[9] == "18.0" and priced[10] == f"{101 - 101 * 100 / 118:.2f}"
    free = rows["SEED00000"]    # i=0: no price
    assert free[8] == "" and free[10] == ""


def test_export_neutralises_spreadsheet_formulas(client, auth_headers):
    with _session() as s:
        s.execute(insert(BookingRow), [dict(
            id="evil-1", bookingRef="EVIL0001", court_id="court-cricket", slotId="evil-slot", name='=HYPERLINK("http://evil","click")',
            contact="+919999999999", contact_norm="+919999999999", sportSlug="cricket", date="2026-11-01", startTime="06:00",
            endTime="07:00", party_size=1, status="pending", createdAt="2026-01-01T00:00:00+00:00", is_primary=True,
            paymentStatus="unpaid", promo_code="@SUM(A1)")])
    row = _rows(_export(client, auth_headers))[1]
    assert row[1].startswith("'=HYPERLINK") and row[2] == "'+919999999999" and row[11] == "'@SUM(A1)"
    raw = _export(client, auth_headers).content.decode("utf-8-sig")
    assert raw.splitlines()[1].startswith('"EVIL0001"')  # every cell quoted


def test_export_reads_with_a_single_streaming_query(client, seeded):
    with count_statements("from bookings") as stmts:
        r = _export(client, seeded)
    assert r.status_code == 200 and len(_rows(r)) - 1 == N
    assert len(stmts) == 1  # one SELECT; no COUNT, no per-row queries


def test_csv_is_produced_in_bounded_chunks(seeded):
    """The HTTP test client glues a response body together, so check the generator itself:
    header chunk first, then ~200 rows at a time, never one giant string."""
    from routes.admin.bookings import _csv_stream
    chunks = list(_csv_stream(deps.booking_repo.iter_primary(batch=100)))
    assert len(chunks) >= N // 200 + 1
    assert chunks[0].startswith("﻿") and chunks[0].count("\n") == 1  # header only
    assert max(len(c) for c in chunks) < 200 * 400  # a chunk is a few tens of KB at most
    assert sum(c.count("\r\n") for c in chunks) == N + 1


def test_iter_primary_is_a_lazy_generator(seeded):
    import inspect
    gen = deps.booking_repo.iter_primary(batch=100)
    assert inspect.isgenerator(gen)
    assert next(gen).bookingRef.startswith("SEED")


def test_export_excludes_deleted_and_is_audited(client, auth_headers):
    _seed_bookings(30)
    victim = next(b for b in _list(client, auth_headers, status="cancelled", limit=100)["items"])
    assert client.delete(f"/api/v1/admin/bookings/{victim['id']}", headers=auth_headers).status_code == 204
    refs = [r[0] for r in _rows(_export(client, auth_headers))[1:]]
    assert victim["bookingRef"] not in refs
    only = [r[0] for r in _rows(_export(client, auth_headers, deleted="only"))[1:]]
    assert only == [victim["bookingRef"]]
    row = next(r for r in deps.audit_repo.query(action="booking.export")[0])
    assert row.actor == "admin" and json.loads(row.detail)["deleted"] in ("no", "only")


def test_export_access_control(client, auth_headers):
    client.cookies.clear()
    assert client.get("/api/v1/admin/bookings/export").status_code == 401
    name = f"cashier_{uuid.uuid4().hex[:6]}"
    deps.user_repo.create(UserRecord(id=str(uuid.uuid4()), username=name, hashed_password=hash_password("1234"), role="cashier",
                                     createdAt=datetime.now(timezone.utc).isoformat(), createdBy="admin"))
    h = {"Authorization": f"Bearer {create_cashier_token(name, 'cashier')}"}
    assert client.get("/api/v1/admin/bookings/export", headers=h).status_code == 403
    assert client.get("/api/v1/admin/bookings/export?deleted=zzz", headers=auth_headers).status_code == 422


# ── customers and enquiries ────────────────────────────────────────────────

def _seed_enquiries(n=1200):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with _session() as s:
        s.execute(insert(EnquiryRow), [dict(
            id=f"enq-{i:05d}", type="corporate" if i % 4 == 0 else "contact", name=f"Name {i}", contact=f"9{i:09d}",
            status="handled" if i % 3 == 0 else "new", createdAt=(base + timedelta(minutes=i)).isoformat()) for i in range(n)])


def test_enquiries_page_in_sql_with_total_header_newest_first(client, auth_headers):
    _seed_enquiries()
    r = client.get("/api/v1/admin/enquiries?limit=50&offset=0", headers=auth_headers)
    assert r.status_code == 200 and r.headers["x-total-count"] == "1200" and len(r.json()) == 50
    assert r.json()[0]["id"] == "enq-01199"  # newest first
    r2 = client.get("/api/v1/admin/enquiries?limit=50&offset=50", headers=auth_headers)
    assert r2.json()[0]["id"] == "enq-01149"
    f = client.get("/api/v1/admin/enquiries?type=corporate&status=new&limit=1000", headers=auth_headers)
    expected = sum(1 for i in range(1200) if i % 4 == 0 and i % 3 != 0)
    assert int(f.headers["x-total-count"]) == expected == len(f.json())
    assert all(e["type"] == "corporate" and e["status"] == "new" for e in f.json())


def test_enquiries_use_two_queries(client, auth_headers):
    _seed_enquiries(300)
    with count_statements("from enquiries") as stmts:
        client.get("/api/v1/admin/enquiries?limit=20", headers=auth_headers)
    assert len(stmts) == 2


def test_customers_page_in_sql_with_total_header(client, auth_headers):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with _session() as s:
        s.execute(insert(CustomerRow), [dict(id=f"cust-{i:05d}", name=f"C{i}", phone=f"8{i:09d}",
                                             createdAt=(base + timedelta(minutes=i)).isoformat()) for i in range(700)])
    r = client.get("/api/v1/admin/customers?limit=100&offset=0", headers=auth_headers)
    assert r.headers["x-total-count"] == "700" and len(r.json()) == 100 and r.json()[0]["id"] == "cust-00699"
    assert len(client.get("/api/v1/admin/customers?limit=100&offset=650", headers=auth_headers).json()) == 50
    with count_statements("from customers") as stmts:
        client.get("/api/v1/admin/customers?limit=10", headers=auth_headers)
    assert len(stmts) == 2


def test_total_count_header_is_readable_by_browsers(client):
    r = client.options("/api/v1/admin/enquiries", headers={"Origin": "http://localhost:5174", "Access-Control-Request-Method": "GET"})
    assert r.status_code == 200
    got = client.get("/api/v1/venue", headers={"Origin": "http://localhost:5174"})
    assert "x-total-count" in got.headers.get("access-control-expose-headers", "").lower()


# ── indexes and contact_norm ───────────────────────────────────────────────

def test_hot_query_indexes_exist():
    with _session() as s:
        names = {r[1] for r in s.execute(text("PRAGMA index_list(bookings)")).all()}
        assert {"ix_bookings_bookingRef", "ix_bookings_contact_norm", "ix_bookings_date_status",
                "ix_bookings_status_created", "ix_bookings_email_lower", "uq_active_court_slot"} <= names
        assert "ix_enquiries_createdAt" in {r[1] for r in s.execute(text("PRAGMA index_list(enquiries)")).all()}
        assert "ix_customers_createdAt" in {r[1] for r in s.execute(text("PRAGMA index_list(customers)")).all()}


def _tomorrow():
    return (date.today() + timedelta(days=1)).isoformat()


def _book(client, contact="9876543210", slot_index=0, **extra):
    slots = [s for s in client.get(f"/api/v1/slots?sport=cricket&date={_tomorrow()}").json() if s["available"]]
    slot = slots[slot_index]
    r = client.post("/api/v1/bookings", json={"name": "Jane", "contact": contact, "slotIds": [slot["id"]], "sportSlug": "cricket",
                                              "date": slot["date"], "startTime": slot["startTime"], "players": 1, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _admin(client, h, ref, **params):
    q = "&".join(f"{k}={v}" for k, v in {"limit": 100, **params}.items())
    items = client.get(f"/api/v1/admin/bookings?{q}", headers=h).json()["items"]
    return next((b for b in items if b["bookingRef"] == ref), None)


def test_contact_norm_is_written_on_create_and_drives_the_pending_cap(client):
    _book(client, contact="Jane@Example.COM ")
    with _session() as s:
        assert s.query(BookingRow).filter(BookingRow.contact_norm == "jane@example.com").count() == 1
    _book(client, contact="jane@example.com", slot_index=2)
    r = client.post("/api/v1/bookings", json={"name": "J", "contact": "JANE@example.com", "slotIds": [
        [s for s in client.get(f"/api/v1/slots?sport=cricket&date={_tomorrow()}").json() if s["available"]][4]["id"]],
        "sportSlug": "cricket", "date": _tomorrow(), "startTime": "09:00", "players": 1})
    assert r.status_code == 429  # same person in three spellings still hits the cap of 2


# ── soft delete ────────────────────────────────────────────────────────────

def _slot_free(client, ab):
    slots = client.get(f"/api/v1/slots?sport={ab['sportSlug']}&date={ab['date']}").json()
    return next(s for s in slots if s["id"] == ab["slotId"])["available"]


def test_soft_delete_hides_the_booking_everywhere_but_keeps_the_row(client, auth_headers):
    b = _book(client)
    ab = _admin(client, auth_headers, b["bookingRef"])
    assert client.delete(f"/api/v1/admin/bookings/{ab['id']}", headers=auth_headers).status_code == 204

    assert _admin(client, auth_headers, b["bookingRef"]) is None                       # gone from the default list
    gone = _admin(client, auth_headers, b["bookingRef"], deleted="only")
    assert gone and gone["deleted_at"] and gone["deleted_by"] == "admin" and gone["status"] == "cancelled"
    assert _admin(client, auth_headers, b["bookingRef"], deleted="all") is not None
    assert client.get(f"/api/v1/bookings/lookup?ref={b['bookingRef']}&contact=9876543210").status_code == 404
    assert _slot_free(client, ab) is True                                              # slot is bookable again
    with _session() as s:
        assert s.query(BookingRow).filter(BookingRow.bookingRef == b["bookingRef"]).count() == 1  # still in the books


def test_deleting_an_active_booking_cancels_it_and_tells_the_customer(client, auth_headers, monkeypatch):
    import services.notification_service as ns
    sent = []
    monkeypatch.setattr(ns, "notification_provider", type("M", (), {"name": "m", "send": lambda self, to, subj, body: (sent.append(subj), __import__("integrations.notifications.base", fromlist=["x"]).NotificationResult(status="sent"))[1]})())
    b = _book(client, contact="del@example.com", email="del@example.com")
    sent.clear()
    ab = _admin(client, auth_headers, b["bookingRef"])
    client.delete(f"/api/v1/admin/bookings/{ab['id']}", headers=auth_headers)
    assert any("cancel" in s.lower() for s in sent)
    row = next(r for r in deps.audit_repo.query(action="booking.delete")[0])
    d = json.loads(row.detail)
    assert d["status"] == "pending" and d["cancelledByDelete"] is True and d["bookingRef"] == b["bookingRef"]


def test_deleting_twice_or_a_missing_booking(client, auth_headers):
    b = _book(client)
    ab = _admin(client, auth_headers, b["bookingRef"])
    assert client.delete(f"/api/v1/admin/bookings/{ab['id']}", headers=auth_headers).status_code == 204
    assert client.delete(f"/api/v1/admin/bookings/{ab['id']}", headers=auth_headers).status_code == 409
    assert client.delete("/api/v1/admin/bookings/nope", headers=auth_headers).status_code == 404


def _pay(client, b):
    return client.post(f"/api/v1/bookings/{b['bookingRef']}/payment/verify", json={
        "providerOrderId": b["checkout"]["providerOrderId"], "providerPaymentId": f"noop_pay_{uuid.uuid4().hex[:6]}"})


def test_a_booking_holding_money_cannot_be_deleted_until_refunded(client, auth_headers):
    b = _book(client)
    _pay(client, b)
    ab = _admin(client, auth_headers, b["bookingRef"])
    r = client.delete(f"/api/v1/admin/bookings/{ab['id']}", headers=auth_headers)
    assert r.status_code == 409 and "refund" in r.json()["detail"].lower()
    client.post(f"/api/v1/admin/bookings/{ab['id']}/refund", json={"amount": 100}, headers=auth_headers)  # partial
    assert client.delete(f"/api/v1/admin/bookings/{ab['id']}", headers=auth_headers).status_code == 409
    client.post(f"/api/v1/admin/bookings/{ab['id']}/refund", json={}, headers=auth_headers)              # the rest
    assert client.delete(f"/api/v1/admin/bookings/{ab['id']}", headers=auth_headers).status_code == 204


def _preorder(client, auth_headers, b):
    cat = client.post("/api/v1/admin/cafe/categories", json={"name": f"C{uuid.uuid4().hex[:5]}", "kind": "food"}, headers=auth_headers).json()["id"]
    item = client.post("/api/v1/admin/cafe/items", json={"category_id": cat, "name": "Tea", "price": 20.0, "taxRatePercent": 5.0}, headers=auth_headers).json()
    r = client.post(f"/api/v1/bookings/{b['bookingRef']}/preorder", json={"contact": "9876543210", "items": [{"menu_item_id": item["id"], "qty": 1}]})
    assert r.status_code == 201, r.text


def test_a_booking_with_cafe_orders_cannot_be_deleted_or_purged(client, auth_headers):
    b = _book(client)
    _pay(client, b)
    ab = _admin(client, auth_headers, b["bookingRef"])
    _preorder(client, auth_headers, b)
    client.post(f"/api/v1/admin/bookings/{ab['id']}/refund", json={}, headers=auth_headers)  # money back, order remains
    r = client.delete(f"/api/v1/admin/bookings/{ab['id']}", headers=auth_headers)
    assert r.status_code == 409 and "café orders" in r.json()["detail"].lower()
    assert client.delete(f"/api/v1/admin/bookings/{ab['id']}/purge", headers=auth_headers).status_code == 409


def test_a_late_payment_for_a_deleted_booking_is_refunded_not_revived(client, auth_headers):
    b = _book(client)
    ab = _admin(client, auth_headers, b["bookingRef"])
    client.delete(f"/api/v1/admin/bookings/{ab['id']}", headers=auth_headers)  # customer still has a live checkout
    r = client.post("/api/v1/payments/razorpay/webhook", content=json.dumps({
        "providerOrderId": b["checkout"]["providerOrderId"], "providerPaymentId": "noop_pay_after_delete"}))
    assert r.status_code == 200 and r.json()["status"] == "late_refunded"
    gone = _admin(client, auth_headers, b["bookingRef"], deleted="only")
    assert gone["status"] == "cancelled" and gone["paymentStatus"] == "unpaid"


# ── restore ────────────────────────────────────────────────────────────────

def test_restore_brings_it_back_cancelled_without_rebooking_the_slot(client, auth_headers):
    b = _book(client)
    ab = _admin(client, auth_headers, b["bookingRef"])
    client.delete(f"/api/v1/admin/bookings/{ab['id']}", headers=auth_headers)
    r = client.post(f"/api/v1/admin/bookings/{ab['id']}/restore", headers=auth_headers)
    assert r.status_code == 200 and r.json()["deleted_at"] is None and r.json()["status"] == "cancelled"
    assert _admin(client, auth_headers, b["bookingRef"]) is not None
    assert _slot_free(client, ab) is True
    assert client.post(f"/api/v1/admin/bookings/{ab['id']}/restore", headers=auth_headers).status_code == 409
    assert client.post("/api/v1/admin/bookings/nope/restore", headers=auth_headers).status_code == 404
    assert deps.audit_repo.query(action="booking.restore")[1] == 1


# ── purge ──────────────────────────────────────────────────────────────────

def test_purge_removes_a_booking_and_its_dev_payment_rows_for_good(client, auth_headers):
    b = _book(client)
    ab = _admin(client, auth_headers, b["bookingRef"])
    assert client.delete(f"/api/v1/admin/bookings/{ab['id']}/purge", headers=auth_headers).status_code == 204
    assert _admin(client, auth_headers, b["bookingRef"], deleted="all") is None
    assert deps.booking_payment_repo.list_by_ref(b["bookingRef"]) == []
    row = next(r for r in deps.audit_repo.query(action="booking.purge")[0])
    assert json.loads(row.detail)["bookingRef"] == b["bookingRef"]


def test_purge_is_refused_for_a_real_payment_record(client, auth_headers):
    b = _book(client)
    _pay(client, b)
    ab = _admin(client, auth_headers, b["bookingRef"])
    pay = deps.booking_payment_repo.get_by_ref(b["bookingRef"])
    with _session() as s:  # pretend this was a live Razorpay payment, not a dev one
        s.execute(text("UPDATE booking_payments SET provider = 'razorpay' WHERE id = :i"), {"i": pay.id})
    r = client.delete(f"/api/v1/admin/bookings/{ab['id']}/purge", headers=auth_headers)
    assert r.status_code == 409 and "real payment" in r.json()["detail"]
    assert _admin(client, auth_headers, b["bookingRef"]) is not None


def test_purge_is_superadmin_only(client, auth_headers):
    b = _book(client)
    ab = _admin(client, auth_headers, b["bookingRef"])
    client.post("/api/v1/admin/users", json={"username": "mgr_purge", "password": "password123"}, headers=auth_headers)
    tok = client.post("/api/v1/admin/login", json={"username": "mgr_purge", "password": "password123"}).json()["access_token"]
    assert client.delete(f"/api/v1/admin/bookings/{ab['id']}/purge", headers={"Authorization": f"Bearer {tok}"}).status_code == 403
    assert client.delete("/api/v1/admin/bookings/nope/purge", headers=auth_headers).status_code == 404
    assert _admin(client, auth_headers, b["bookingRef"]) is not None
