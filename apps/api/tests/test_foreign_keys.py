"""Workstream H: real foreign keys on bookings/orders, the orphan audit and the migration on dirty data.

The migration tests drive alembic and the real boot path in subprocesses against throwaway databases.
Set DAZY_TEST_PG_URL to a THROWAWAY PostgreSQL database (its name must contain "test") to run the same
dirty-data migration against Postgres; it is skipped otherwise."""
import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

import deps
from db import _session, engine
from fk_integrity import RELATIONS, find_orphans, repair

API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRE_FK = "n7o8p9q0r1s2"   # last revision before the foreign keys
NOW = datetime.now(timezone.utc).isoformat()


@pytest.fixture(autouse=True)
def _clean_test_orders():
    """conftest does not reset café orders between tests; this file's orders are tagged createdBy='t'."""
    def wipe():
        with _session() as s:
            s.execute(text("DELETE FROM orders WHERE \"createdBy\" = 't'"))
    wipe()
    yield
    wipe()


# ── helpers ────────────────────────────────────────────────────────────────

def _booking(**kw):
    base = dict(id=str(uuid.uuid4()), bookingRef=uuid.uuid4().hex[:8].upper(), slotId=f"slot-{uuid.uuid4().hex}",
                name="T", contact="9000000000", sportSlug="cricket", date="2026-12-01", startTime="06:00",
                endTime="07:00", party_size=1, status="pending", createdAt=NOW, is_primary=True,
                paymentStatus="unpaid", court_id="court-cricket", customer_id=None)
    base.update(kw)
    return base


def _insert(conn, table, **values):
    cols = ", ".join(f'"{c}"' for c in values)
    params = ", ".join(f":{c}" for c in values)
    conn.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({params})"), values)


def _order(**kw):
    base = dict(id=str(uuid.uuid4()), orderNo=f"O-{uuid.uuid4().hex[:6]}", orderType="takeaway", status="open",
                createdBy="t", createdAt=NOW, updatedAt=NOW)
    base.update(kw)
    return base


def _customer(cid=None, phone=None):
    return dict(id=cid or str(uuid.uuid4()), name="C", phone=phone or f"7{uuid.uuid4().int % 10**9:09d}", createdAt=NOW)


def _raw_insert_ignoring_fks(rows_by_table):
    """Insert rows through a plain sqlite3 connection (foreign keys OFF, as in a pre-migration database)."""
    path = engine.url.database
    con = sqlite3.connect(path)
    try:
        con.execute("PRAGMA foreign_keys=OFF")
        for table, rows in rows_by_table:
            for row in rows:
                cols = ", ".join(f'"{c}"' for c in row)
                con.execute(f"INSERT INTO {table} ({cols}) VALUES ({', '.join('?' for _ in row)})", list(row.values()))
        con.commit()
    finally:
        con.close()


# ── enforcement and delete rules ───────────────────────────────────────────

def test_sqlite_connections_enforce_foreign_keys():
    with _session() as s:
        assert s.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_constraints_are_declared_with_the_intended_delete_rules():
    with _session() as s:
        def fks(table):
            return {(r[3], r[2], r[6]) for r in s.execute(text(f"PRAGMA foreign_key_list({table})")).all()}
        assert ("court_id", "courts", "RESTRICT") in fks("bookings")
        assert ("customer_id", "customers", "SET NULL") in fks("bookings")
        assert ("customer_id", "customers", "SET NULL") in fks("orders")
        assert ("booking_id", "bookings", "SET NULL") in fks("orders")


@pytest.mark.parametrize("table,row", [
    ("bookings", lambda: _booking(court_id="court-does-not-exist")),
    ("bookings", lambda: _booking(customer_id="ghost-customer")),
    ("orders", lambda: _order(booking_id="ghost-booking")),
    ("orders", lambda: _order(customer_id="ghost-customer")),
])
def test_dangling_references_are_rejected(table, row):
    with pytest.raises(IntegrityError):
        with _session() as s:
            _insert(s, table, **row())


def test_valid_references_are_accepted():
    cust = _customer()
    b = _booking(customer_id=cust["id"])
    with _session() as s:
        _insert(s, "customers", **cust)
        _insert(s, "bookings", **b)
        _insert(s, "orders", **_order(booking_id=b["id"], customer_id=cust["id"]))


def test_deleting_a_customer_unlinks_their_bookings_and_orders():
    cust = _customer()
    b = _booking(customer_id=cust["id"])
    o = _order(customer_id=cust["id"], booking_id=b["id"])
    with _session() as s:
        _insert(s, "customers", **cust)
        _insert(s, "bookings", **b)
        _insert(s, "orders", **o)
    with _session() as s:
        s.execute(text("DELETE FROM customers WHERE id = :i"), {"i": cust["id"]})
    with _session() as s:
        assert s.execute(text("SELECT customer_id FROM bookings WHERE id = :i"), {"i": b["id"]}).scalar() is None
        row = s.execute(text("SELECT customer_id, booking_id FROM orders WHERE id = :i"), {"i": o["id"]}).one()
        assert row[0] is None and row[1] == b["id"]  # the order keeps its booking link


def test_deleting_a_booking_keeps_its_order():
    b = _booking()
    o = _order(booking_id=b["id"])
    with _session() as s:
        _insert(s, "bookings", **b)
        _insert(s, "orders", **o)
    with _session() as s:
        s.execute(text("DELETE FROM bookings WHERE id = :i"), {"i": b["id"]})
    with _session() as s:
        assert s.execute(text("SELECT booking_id FROM orders WHERE id = :i"), {"i": o["id"]}).one()[0] is None


def test_a_court_with_bookings_cannot_be_deleted_but_can_be_deactivated(client, auth_headers):
    court = client.post("/api/v1/admin/courts", json={"venue_id": "venue-dazy", "sport": "badminton", "name": "Court 9", "capacity": 1},
                        headers=auth_headers).json()
    with _session() as s:
        _insert(s, "bookings", **_booking(court_id=court["id"], sportSlug="badminton"))
    with pytest.raises(IntegrityError):
        with _session() as s:
            s.execute(text("DELETE FROM courts WHERE id = :i"), {"i": court["id"]})
    assert client.delete(f"/api/v1/admin/courts/{court['id']}", headers=auth_headers).status_code == 204  # deactivate path
    empty = client.post("/api/v1/admin/courts", json={"venue_id": "venue-dazy", "sport": "pickleball", "name": "Court 8", "capacity": 1},
                        headers=auth_headers).json()
    with _session() as s:  # a court with no bookings can still be removed (schedule rules cascade is not declared, so none exist)
        s.execute(text("DELETE FROM courts WHERE id = :i"), {"i": empty["id"]})


# ── orphan audit and repair ────────────────────────────────────────────────

def _dirty_rows():
    good_cust = _customer()
    return good_cust, [
        ("customers", [good_cust]),
        ("bookings", [
            _booking(id="b-ok", bookingRef="BOK00001", court_id="court-cricket", customer_id=good_cust["id"]),
            _booking(id="b-court-remap", bookingRef="BCR00001", court_id="court-gone", sportSlug="cricket"),     # one cricket court
            _booking(id="b-court-null", bookingRef="BCN00001", court_id="court-gone", sportSlug="padel"),        # no such sport court
            _booking(id="b-cust", bookingRef="BCU00001", customer_id="cust-gone"),
        ]),
        ("orders", [
            _order(id="o-ok", booking_id="b-ok", customer_id=good_cust["id"]),
            _order(id="o-booking", booking_id="booking-gone"),
            _order(id="o-cust", customer_id="cust-gone"),
        ]),
    ]


def test_orphan_audit_reports_counts_and_samples_without_changing_anything():
    _, rows = _dirty_rows()
    _raw_insert_ignoring_fks(rows)
    with engine.connect() as conn:
        reports = {r.relation.label: r for r in find_orphans(conn)}
        assert reports["bookings.court_id -> courts.id"].count == 2
        assert reports["bookings.customer_id -> customers.id"].count == 1
        assert reports["orders.customer_id -> customers.id"].count == 1
        assert reports["orders.booking_id -> bookings.id"].count == 1
        court = reports["bookings.court_id -> courts.id"]
        assert set(court.sample_ids) == {"b-court-remap", "b-court-null"} and set(court.sample_values) == {"court-gone"}
        again = {r.relation.label: r.count for r in find_orphans(conn)}
        assert sum(again.values()) == 5  # read-only
    assert len(RELATIONS) == 4


def test_repair_remaps_or_nulls_and_deletes_nothing():
    good_cust, rows = _dirty_rows()
    _raw_insert_ignoring_fks(rows)
    with _session() as s:
        before = {t: s.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in ("bookings", "orders", "customers")}
        changed = repair(s.connection())
        assert changed["bookings.court_id -> courts.id"] == 2
        after = {t: s.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in ("bookings", "orders", "customers")}
        assert before == after  # nothing deleted
        court = lambda i: s.execute(text("SELECT court_id FROM bookings WHERE id = :i"), {"i": i}).scalar()  # noqa: E731
        assert court("b-court-remap") == "court-cricket" and court("b-court-null") is None and court("b-ok") == "court-cricket"
        assert s.execute(text("SELECT customer_id FROM bookings WHERE id = 'b-cust'")).scalar() is None
        assert s.execute(text("SELECT customer_id FROM bookings WHERE id = 'b-ok'")).scalar() == good_cust["id"]
        assert s.execute(text("SELECT booking_id FROM orders WHERE id = 'o-booking'")).scalar() is None
        assert s.execute(text("SELECT booking_id FROM orders WHERE id = 'o-ok'")).scalar() == "b-ok"
        assert sum(r.count for r in find_orphans(s.connection())) == 0


def test_remap_leaves_the_link_empty_when_a_sport_has_several_courts(client, auth_headers):
    client.post("/api/v1/admin/courts", json={"venue_id": "venue-dazy", "sport": "cricket", "name": "Court 2", "capacity": 1}, headers=auth_headers)
    _raw_insert_ignoring_fks([("bookings", [_booking(id="b-amb", bookingRef="BAM00001", court_id="court-gone", sportSlug="cricket")])])
    with _session() as s:
        repair(s.connection())
        assert s.execute(text("SELECT court_id FROM bookings WHERE id = 'b-amb'")).scalar() is None  # ambiguous: do not guess


# ── scripts/check_fk_orphans.py and the migration, in subprocesses ─────────

def _env(db_url):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("DAZY_", "RENDER", "R2_", "TURNSTILE"))}
    env.update({"DAZY_DB_URL": db_url, "PYTHONIOENCODING": "utf-8"})
    return env


def _run(args, db_url, check=True):
    r = subprocess.run([sys.executable, *args], cwd=API_DIR, env=_env(db_url), capture_output=True, text=True, timeout=240)
    if check and r.returncode != 0:
        raise AssertionError(f"{args} failed ({r.returncode}):\n{r.stdout}\n{r.stderr}")
    return r


def _alembic(cmd, rev, db_url):
    return _run(["-m", "alembic", cmd, rev], db_url)


def _boot(db_url):
    """The real startup path: init_db() runs every pending migration, then verifies foreign keys."""
    return _run(["-c", "import db; db.init_db()"], db_url)


@pytest.fixture
def sqlite_url(tmp_path):
    return f"sqlite:///{(tmp_path / 'mig.db').as_posix()}"


def _sql(db_url, sql, params=()):
    con = sqlite3.connect(db_url.removeprefix("sqlite:///"))
    try:
        con.execute("PRAGMA foreign_keys=OFF")
        rows = con.execute(sql, params).fetchall()
        con.commit()
        return rows
    finally:
        con.close()


def _seed_pre_fk(db_url):
    """A pre-migration database with valid and dangling links (the shape production may be in)."""
    con = sqlite3.connect(db_url.removeprefix("sqlite:///"))
    con.execute("PRAGMA foreign_keys=OFF")

    def ins(table, **v):
        info = con.execute(f"PRAGMA table_info({table})").fetchall()
        for _cid, name, ctype, notnull, default, _pk in info:  # fill required columns we do not care about
            if name not in v and notnull and default is None:
                v[name] = 0 if ("INT" in ctype.upper() or "NUMERIC" in ctype.upper() or "BOOL" in ctype.upper()) else "x"
        con.execute(f"INSERT INTO {table} ({', '.join(chr(34) + k + chr(34) for k in v)}) VALUES ({', '.join('?' for _ in v)})", list(v.values()))

    ins("venues", id="venue-dazy", name="V", timezone="Asia/Kolkata", active=1, createdAt=NOW)
    ins("courts", id="court-cricket", venue_id="venue-dazy", sport="cricket", name="C1", capacity=1, active=1, createdAt=NOW)
    ins("courts", id="court-bad-1", venue_id="venue-dazy", sport="badminton", name="B1", capacity=1, active=1, createdAt=NOW)
    ins("courts", id="court-bad-2", venue_id="venue-dazy", sport="badminton", name="B2", capacity=1, active=1, createdAt=NOW)
    ins("customers", id="cust-1", name="C", phone="7000000001", createdAt=NOW)
    base = dict(contact="9", date="2026-12-01", startTime="06:00", endTime="07:00", party_size=1, status="confirmed",
                createdAt=NOW, is_primary=1, paymentStatus="unpaid", name="N")
    ins("bookings", id="b-ok", bookingRef="OK000001", slotId="s1", sportSlug="cricket", court_id="court-cricket", customer_id="cust-1", **base)
    ins("bookings", id="b-remap", bookingRef="RM000001", slotId="s2", sportSlug="cricket", court_id="court-gone", **base)
    ins("bookings", id="b-amb", bookingRef="AM000001", slotId="s3", sportSlug="badminton", court_id="court-gone", **base)
    ins("bookings", id="b-cust", bookingRef="CU000001", slotId="s4", sportSlug="cricket", court_id="court-cricket", customer_id="cust-gone", **base)
    ins("orders", id="o-ok", orderNo="O1", orderType="takeaway", status="open", createdBy="t", createdAt=NOW, updatedAt=NOW, booking_id="b-ok")
    ins("orders", id="o-bk", orderNo="O2", orderType="takeaway", status="open", createdBy="t", createdAt=NOW, updatedAt=NOW, booking_id="b-gone")
    ins("orders", id="o-cu", orderNo="O3", orderType="takeaway", status="open", createdBy="t", createdAt=NOW, updatedAt=NOW, customer_id="cust-gone")
    con.commit()
    con.close()


def test_orphan_script_reports_then_repairs(sqlite_url):
    _alembic("upgrade", PRE_FK, sqlite_url)
    _seed_pre_fk(sqlite_url)
    report = _run(["scripts/check_fk_orphans.py"], sqlite_url, check=False)
    assert report.returncode == 1
    out = report.stdout
    assert "bookings.court_id -> courts.id: 2 orphan" in out and "bookings.customer_id -> customers.id: 1 orphan" in out
    assert "orders.booking_id -> bookings.id: 1 orphan" in out and "Nothing was changed" in out
    assert "court-gone" in out and "mig.db" in out
    assert _sql(sqlite_url, "SELECT court_id FROM bookings WHERE id = 'b-remap'") == [("court-gone",)]  # read-only really is

    fixed = _run(["scripts/check_fk_orphans.py", "--repair"], sqlite_url, check=False)
    assert fixed.returncode == 0 and "Orphans remaining: 0" in fixed.stdout
    assert _run(["scripts/check_fk_orphans.py"], sqlite_url).stdout.count("No orphans") == 1


def test_orphan_script_redacts_credentials_in_its_header():
    sys.path.insert(0, API_DIR)
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_fk_orphans", os.path.join(API_DIR, "scripts", "check_fk_orphans.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._redacted("postgresql://user:s3cret@host.neon.tech/db") == "postgresql://***@host.neon.tech/db"
    assert "s3cret" not in mod._redacted("postgresql://user:s3cret@host.neon.tech/db")


def test_migration_repairs_dirty_data_adds_constraints_and_keeps_the_special_indexes(sqlite_url):
    _alembic("upgrade", PRE_FK, sqlite_url)
    _seed_pre_fk(sqlite_url)
    counts = {t: _sql(sqlite_url, f"SELECT COUNT(*) FROM {t}")[0][0] for t in ("bookings", "orders", "customers", "courts")}

    _boot(sqlite_url)  # real boot path: migrate to head, then PRAGMA foreign_key_check

    # nothing lost
    assert {t: _sql(sqlite_url, f"SELECT COUNT(*) FROM {t}")[0][0] for t in counts} == counts
    # repaired
    court = lambda i: _sql(sqlite_url, "SELECT court_id FROM bookings WHERE id = ?", (i,))[0][0]  # noqa: E731
    assert court("b-ok") == "court-cricket"
    assert court("b-remap") == "court-cricket"       # its sport has exactly one court
    assert court("b-amb") is None                    # badminton has two: never guess
    assert _sql(sqlite_url, "SELECT customer_id FROM bookings WHERE id = 'b-cust'") == [(None,)]
    assert _sql(sqlite_url, "SELECT customer_id FROM bookings WHERE id = 'b-ok'") == [("cust-1",)]
    assert _sql(sqlite_url, "SELECT booking_id FROM orders WHERE id = 'o-bk'") == [(None,)]
    assert _sql(sqlite_url, "SELECT booking_id FROM orders WHERE id = 'o-ok'") == [("b-ok",)]
    assert _sql(sqlite_url, "SELECT customer_id FROM orders WHERE id = 'o-cu'") == [(None,)]
    # constraints exist
    fks = {(r[3], r[2], r[6]) for r in _sql(sqlite_url, "PRAGMA foreign_key_list(bookings)")}
    assert {("court_id", "courts", "RESTRICT"), ("customer_id", "customers", "SET NULL")} <= fks
    fks = {(r[3], r[2], r[6]) for r in _sql(sqlite_url, "PRAGMA foreign_key_list(orders)")}
    assert {("customer_id", "customers", "SET NULL"), ("booking_id", "bookings", "SET NULL")} <= fks
    assert _sql(sqlite_url, "PRAGMA foreign_key_check") == [] and _sql(sqlite_url, "PRAGMA integrity_check") == [("ok",)]
    # the table rebuild must not have lost the partial unique index or the expression index
    ddl = {r[0]: r[1] for r in _sql(sqlite_url, "SELECT name, sql FROM sqlite_master WHERE type = 'index' AND tbl_name = 'bookings'")}
    assert "WHERE status NOT IN ('cancelled', 'no_show')" in ddl["uq_active_court_slot"]
    assert "lower(email)" in ddl["ix_bookings_email_lower"]
    for name in ("ix_bookings_bookingRef", "ix_bookings_contact_norm", "ix_bookings_date_status", "ix_bookings_status_created"):
        assert name in ddl, name
    # ... and the partial index still does its job: a second ACTIVE booking of the same slot is refused, a cancelled one is not
    dup = dict(contact="9", date="2026-12-01", startTime="06:00", endTime="07:00", party_size=1, createdAt=NOW, is_primary=1,
               paymentStatus="unpaid", name="N", sportSlug="cricket", court_id="court-cricket", slotId="s1")
    cols = ", ".join(dup) + ", id, bookingRef, status"
    qs = ", ".join("?" for _ in range(len(dup) + 3))
    with pytest.raises(sqlite3.IntegrityError):
        _sql(sqlite_url, f"INSERT INTO bookings ({cols}) VALUES ({qs})", (*dup.values(), "dup1", "DUP00001", "pending"))
    _sql(sqlite_url, f"INSERT INTO bookings ({cols}) VALUES ({qs})", (*dup.values(), "dup2", "DUP00002", "cancelled"))


def test_migration_is_clean_on_an_empty_database_and_downgrades_without_losing_rows(sqlite_url):
    _boot(sqlite_url)
    assert _sql(sqlite_url, "PRAGMA foreign_key_check") == []
    _alembic("downgrade", PRE_FK, sqlite_url)
    assert _sql(sqlite_url, "PRAGMA foreign_key_list(orders)") == [] or all(r[2] != "bookings" for r in _sql(sqlite_url, "PRAGMA foreign_key_list(orders)"))
    ddl = {r[0] for r in _sql(sqlite_url, "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'bookings'")}
    assert {"uq_active_court_slot", "ix_bookings_email_lower"} <= ddl


def test_downgrade_keeps_data_and_drops_the_constraints(sqlite_url):
    _alembic("upgrade", PRE_FK, sqlite_url)
    _seed_pre_fk(sqlite_url)
    _boot(sqlite_url)
    before = _sql(sqlite_url, "SELECT COUNT(*) FROM bookings")[0][0]
    _alembic("downgrade", PRE_FK, sqlite_url)
    assert _sql(sqlite_url, "SELECT COUNT(*) FROM bookings")[0][0] == before
    assert all(r[2] != "courts" for r in _sql(sqlite_url, "PRAGMA foreign_key_list(bookings)"))
    assert _sql(sqlite_url, "SELECT court_id FROM bookings WHERE id = 'b-remap'") == [("court-cricket",)]  # repair is not undone


# ── optional: the same dirty-data migration on a real PostgreSQL ────────────

PG_URL = os.environ.get("DAZY_TEST_PG_URL")


@pytest.mark.skipif(not PG_URL, reason="set DAZY_TEST_PG_URL to a throwaway PostgreSQL database to run")
def test_migration_on_postgres_with_dirty_data():
    import psycopg2
    assert "test" in PG_URL.rsplit("/", 1)[-1].split("?")[0].lower(), "refusing to wipe a database whose name lacks 'test'"
    dsn = PG_URL.replace("postgresql+psycopg2://", "postgresql://")

    def pg(sql, params=None, fetch=True):
        con = psycopg2.connect(dsn)
        con.autocommit = True
        try:
            cur = con.cursor()
            cur.execute(sql, params)
            return cur.fetchall() if fetch else None
        finally:
            con.close()

    pg("DROP SCHEMA public CASCADE", fetch=False)
    pg("CREATE SCHEMA public", fetch=False)
    _alembic("upgrade", PRE_FK, PG_URL)
    now = NOW
    pg("INSERT INTO venues (id, name, timezone, active, \"createdAt\") VALUES ('venue-dazy','V','Asia/Kolkata',true,%s)", (now,), fetch=False)
    pg("INSERT INTO courts (id, venue_id, sport, name, capacity, active, \"createdAt\") VALUES ('court-cricket','venue-dazy','cricket','C1',1,true,%s)", (now,), fetch=False)
    pg("INSERT INTO customers (id, name, phone, \"createdAt\") VALUES ('cust-1','C','7000000001',%s)", (now,), fetch=False)
    base = ("'9','2026-12-01','06:00','07:00',1,'confirmed',%s,true,'unpaid','N'")
    cols = '(id,"bookingRef","slotId","sportSlug",court_id,customer_id,contact,date,"startTime","endTime",party_size,status,"createdAt",is_primary,"paymentStatus",name)'
    pg(f"INSERT INTO bookings {cols} VALUES ('b-ok','OK1','s1','cricket','court-cricket','cust-1',{base})", (now,), fetch=False)
    pg(f"INSERT INTO bookings {cols} VALUES ('b-remap','RM1','s2','cricket','court-gone',NULL,{base})", (now,), fetch=False)
    pg(f"INSERT INTO bookings {cols} VALUES ('b-cust','CU1','s3','cricket','court-cricket','cust-gone',{base})", (now,), fetch=False)
    _alembic("upgrade", "head", PG_URL)
    assert pg("SELECT court_id FROM bookings WHERE id = 'b-remap'") == [("court-cricket",)]
    assert pg("SELECT customer_id FROM bookings WHERE id = 'b-cust'") == [(None,)]
    rules = dict(pg("SELECT constraint_name, delete_rule FROM information_schema.referential_constraints WHERE constraint_name LIKE 'fk\\_%'"))
    assert rules["fk_bookings_court"] == "RESTRICT" and rules["fk_bookings_customer"] == "SET NULL"
    assert rules["fk_orders_booking"] == "SET NULL" and rules["fk_orders_customer"] == "SET NULL"
    with pytest.raises(Exception):
        pg("DELETE FROM courts WHERE id = 'court-cricket'", fetch=False)
    _alembic("downgrade", PRE_FK, PG_URL)
    assert not pg("SELECT 1 FROM information_schema.referential_constraints WHERE constraint_name LIKE 'fk\\_bookings%'")
