"""Football shares the cricket turf: one court serves both sports, so a booking under either blocks the other."""
from datetime import date, timedelta

import pytest

import deps


def _day(offset: int = 1) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def _slots(client, sport, day=None):
    return client.get(f"/api/v1/slots?sport={sport}&date={day or _day()}").json()


def _by_id(slots):
    return {s["id"]: s for s in slots}


def _book(client, slot, contact="9876543210", players=1, **kw):
    return client.post("/api/v1/bookings", json={
        "name": "Jane", "contact": contact, "slotIds": [slot["id"]], "sportSlug": slot["sportSlug"],
        "date": slot["date"], "startTime": slot["startTime"], "players": players, **kw})


def _free_slot(client, sport):
    return next(s for s in _slots(client, sport) if s["available"])


# ── seed: football is on the cricket court ──────────────────────────────────

def test_football_has_no_court_of_its_own_but_shares_cricket(client, auth_headers):
    courts = client.get("/api/v1/admin/courts", headers=auth_headers).json()
    assert sorted(c["sport"] for c in courts) == ["badminton", "cricket", "pickleball"]
    by_sport = {c["sport"]: c for c in courts}
    assert by_sport["cricket"]["sports"] == ["cricket", "football"]
    assert by_sport["badminton"]["sports"] == ["badminton"]
    assert by_sport["pickleball"]["sports"] == ["pickleball"]


def test_sports_list_includes_football(client):
    assert "football" in [s["slug"] for s in client.get("/api/v1/sports").json()]


# ── the same slots show for both sports ─────────────────────────────────────

def test_the_same_slots_are_listed_for_football_and_cricket(client):
    cricket, football = _slots(client, "cricket"), _slots(client, "football")
    assert [s["id"] for s in cricket] == [s["id"] for s in football] and football
    assert {s["courtId"] for s in football} == {"court-cricket"}
    # priced from the same court schedule
    assert [s["finalPrice"] for s in cricket] == [s["finalPrice"] for s in football]


def test_a_slot_reports_the_sport_it_was_asked_for(client):
    assert {s["sportSlug"] for s in _slots(client, "football")} == {"football"}
    assert {s["sportSlug"] for s in _slots(client, "cricket")} == {"cricket"}


def test_max_players_is_per_requested_sport(client):
    assert {s["maxPlayers"] for s in _slots(client, "football")} == {25}
    assert {s["maxPlayers"] for s in _slots(client, "cricket")} == {25}
    assert {s["maxPlayers"] for s in _slots(client, "pickleball")} == {4}
    assert {s["maxPlayers"] for s in _slots(client, "badminton")} == {4}


def test_unfiltered_slots_list_the_shared_court_once(client):
    ids = [s["id"] for s in client.get(f"/api/v1/slots?date={_day()}").json() if s["courtId"] == "court-cricket"]
    assert len(ids) == len(set(ids)) == len(_slots(client, "cricket"))


# ── booking one sport blocks the other ──────────────────────────────────────

@pytest.mark.parametrize("first,second", [("football", "cricket"), ("cricket", "football")])
def test_booking_one_sport_blocks_the_slot_for_the_other(client, first, second):
    slot = _free_slot(client, first)
    r = _book(client, slot)
    assert r.status_code == 201, r.text
    assert r.json()["sport"] == first  # stored under the sport it was booked as

    assert _by_id(_slots(client, second))[slot["id"]]["available"] is False
    other = _by_id(_slots(client, second))[slot["id"]]
    r2 = _book(client, other, contact="9111111111")
    assert r2.status_code == 409


def test_other_sports_are_not_blocked(client):
    slot = _free_slot(client, "football")
    assert _book(client, slot).status_code == 201
    for sport in ("badminton", "pickleball"):
        assert all(s["available"] for s in _slots(client, sport))


def test_the_database_blocks_a_race_across_sports(client):
    """Even when both sports pass the availability check, the unique index rejects the second insert."""
    from models import BookingRecord
    import uuid
    from datetime import datetime, timezone
    from sqlalchemy.exc import IntegrityError

    slot = _free_slot(client, "football")

    def rec(sport):
        return BookingRecord(id=str(uuid.uuid4()), bookingRef=uuid.uuid4().hex[:8].upper(), court_id=slot["courtId"],
                             slotId=slot["id"], name="A", contact="9000000000", sportSlug=sport, date=slot["date"],
                             startTime=slot["startTime"], endTime=slot["endTime"], party_size=1, status="pending",
                             createdAt=datetime.now(timezone.utc).isoformat())

    deps.booking_repo.create_many([rec("football")])
    with pytest.raises(IntegrityError):
        deps.booking_repo.create_many([rec("cricket")])


def test_cancelling_frees_the_slot_for_both_sports(client, auth_headers):
    slot = _free_slot(client, "football")
    bid = _book(client, slot).json()
    rows = client.get("/api/v1/admin/bookings?limit=100", headers=auth_headers).json()["items"]
    row = next(b for b in rows if b["bookingRef"] == bid["bookingRef"])
    assert client.patch(f"/api/v1/admin/bookings/{row['id']}", json={"status": "cancelled"}, headers=auth_headers).status_code == 200
    for sport in ("cricket", "football"):
        assert _by_id(_slots(client, sport))[slot["id"]]["available"] is True


def test_football_booking_is_priced_and_promoted_as_football(client):
    slot = _free_slot(client, "football")
    r = _book(client, slot, promoCode="WELCOME10")  # an all-sports promo
    assert r.status_code == 201
    assert r.json()["price"] == pytest.approx(slot["finalPrice"] * 0.9)


def test_25_players_accepted_and_26_rejected(client):
    slot = _free_slot(client, "football")
    assert _book(client, slot, players=26).status_code == 422
    assert _book(client, slot, players=25).status_code == 201


def test_football_is_a_valid_sport_for_enquiries_and_promos(client, auth_headers):
    r = client.post("/api/v1/contact-enquiries",
                    json={"name": "A B", "contact": "9000000001", "message": "football please", "interestedSport": "football"})
    assert r.status_code == 201
    r = client.post("/api/v1/admin/promos", json={"code": "FOOT10", "kind": "percent", "value": 10, "sport_slug": "football"},
                    headers=auth_headers)
    assert r.status_code in (200, 201), r.text


# ── schedule exceptions apply to the court, so to both sports ───────────────

def test_a_holiday_on_the_shared_court_closes_both_sports(client, auth_headers):
    day = _day(2)
    assert _slots(client, "football", day) and _slots(client, "cricket", day)
    r = client.post("/api/v1/admin/schedule/exceptions", json={"court_id": "court-cricket", "day": day, "closed": True},
                    headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    assert _slots(client, "football", day) == [] and _slots(client, "cricket", day) == []


# ── admin: manage which sports a court serves ───────────────────────────────

def test_admin_can_link_and_unlink_a_sport(client, auth_headers):
    courts = {c["sport"]: c for c in client.get("/api/v1/admin/courts", headers=auth_headers).json()}
    pb = courts["pickleball"]
    r = client.patch(f"/api/v1/admin/courts/{pb['id']}", json={"sports": ["pickleball", "football"]}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["sports"] == ["pickleball", "football"]
    football_courts = {s["courtId"] for s in _slots(client, "football")}
    assert football_courts == {"court-cricket", pb["id"]}

    r = client.patch(f"/api/v1/admin/courts/{pb['id']}", json={"sports": ["pickleball"]}, headers=auth_headers)
    assert r.json()["sports"] == ["pickleball"]
    assert {s["courtId"] for s in _slots(client, "football")} == {"court-cricket"}


def test_a_court_must_keep_its_own_sport(client, auth_headers):
    cricket = next(c for c in client.get("/api/v1/admin/courts", headers=auth_headers).json() if c["sport"] == "cricket")
    r = client.patch(f"/api/v1/admin/courts/{cricket['id']}", json={"sports": ["football"]}, headers=auth_headers)
    assert r.status_code == 422


def test_unknown_sport_in_sports_is_rejected(client, auth_headers):
    cricket = next(c for c in client.get("/api/v1/admin/courts", headers=auth_headers).json() if c["sport"] == "cricket")
    r = client.patch(f"/api/v1/admin/courts/{cricket['id']}", json={"sports": ["cricket", "hockey"]}, headers=auth_headers)
    assert r.status_code == 422


def test_a_new_court_can_be_created_shared(client, auth_headers):
    venue = client.get("/api/v1/admin/courts", headers=auth_headers).json()[0]["venue_id"]
    r = client.post("/api/v1/admin/courts", json={"venue_id": venue, "sport": "cricket", "name": "Turf B", "sports": ["football"]},
                    headers=auth_headers)
    assert r.status_code == 201 and r.json()["sports"] == ["cricket", "football"]


def test_unlinking_does_not_touch_existing_bookings(client, auth_headers):
    slot = _free_slot(client, "football")
    assert _book(client, slot).status_code == 201
    cricket = next(c for c in client.get("/api/v1/admin/courts", headers=auth_headers).json() if c["sport"] == "cricket")
    assert client.patch(f"/api/v1/admin/courts/{cricket['id']}", json={"sports": ["cricket"]}, headers=auth_headers).status_code == 200
    assert _slots(client, "football") == []  # nothing new can be booked as football...
    rows = client.get("/api/v1/admin/bookings?limit=100", headers=auth_headers).json()["items"]
    assert [b["sportSlug"] for b in rows] == ["football"]  # ...but the booking made earlier is intact


# ── migration (real Alembic run on a throwaway SQLite database) ──────────────

def _alembic_run(cmd, rev, db_url):
    import os, subprocess, sys
    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {k: v for k, v in os.environ.items() if not k.startswith(("DAZY_", "RENDER", "R2_", "TURNSTILE"))}
    env.update({"DAZY_DB_URL": db_url, "PYTHONIOENCODING": "utf-8"})
    r = subprocess.run([sys.executable, "-m", "alembic", cmd, rev], cwd=api_dir, env=env, capture_output=True, text=True, timeout=240)
    assert r.returncode == 0, f"alembic {cmd} {rev} failed: {r.stdout} {r.stderr}"


def _rows(db_url, sql):
    import sqlite3
    con = sqlite3.connect(db_url.removeprefix("sqlite:///"))
    try:
        return con.execute(sql).fetchall()
    finally:
        con.commit()
        con.close()


def test_migration_links_every_court_and_puts_football_on_the_cricket_turf(tmp_path):
    url = f"sqlite:///{(tmp_path / 'mig.db').as_posix()}"
    _alembic_run("upgrade", "p9q0r1s2t3u4", url)  # the schema before court_sports
    _rows(url, "INSERT INTO venues (id, name, timezone, active, createdAt) VALUES ('v1', 'V', 'Asia/Kolkata', 1, 'now')")
    for cid, sport in (("court-cricket", "cricket"), ("court-badminton", "badminton"), ("court-pickleball", "pickleball")):
        _rows(url, f"INSERT INTO courts (id, venue_id, sport, name, capacity, active, createdAt) "
                   f"VALUES ('{cid}', 'v1', '{sport}', 'Court 1', 1, 1, 'now')")
    _alembic_run("upgrade", "q0r1s2t3u4v5", url)
    assert _rows(url, "SELECT court_id, sport_slug FROM court_sports ORDER BY court_id, sport_slug") == [
        ("court-badminton", "badminton"), ("court-cricket", "cricket"), ("court-cricket", "football"),
        ("court-pickleball", "pickleball")]
    # reversible, and re-appliable
    _alembic_run("downgrade", "p9q0r1s2t3u4", url)
    assert _rows(url, "SELECT name FROM sqlite_master WHERE name = 'court_sports'") == []
    _alembic_run("upgrade", "q0r1s2t3u4v5", url)
    assert len(_rows(url, "SELECT * FROM court_sports")) == 4


def test_migration_on_a_database_without_the_cricket_court_adds_no_football_link(tmp_path):
    url = f"sqlite:///{(tmp_path / 'mig2.db').as_posix()}"
    _alembic_run("upgrade", "p9q0r1s2t3u4", url)
    _rows(url, "INSERT INTO venues (id, name, timezone, active, createdAt) VALUES ('v1', 'V', 'Asia/Kolkata', 1, 'now')")
    _rows(url, "INSERT INTO courts (id, venue_id, sport, name, capacity, active, createdAt) "
               "VALUES ('c-b', 'v1', 'badminton', 'Court 1', 1, 1, 'now')")
    _alembic_run("upgrade", "q0r1s2t3u4v5", url)
    assert _rows(url, "SELECT court_id, sport_slug FROM court_sports") == [("c-b", "badminton")]
