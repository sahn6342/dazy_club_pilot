"""The venue details shown in the website footer: real defaults for new databases, and a data migration that
replaces the old placeholders in existing ones without touching anything an admin edited."""
import os
import sqlite3
import subprocess
import sys

import pytest

ADDRESS = "J29M+RP5 D1, Chamari Chak Rd, Ram Krishna Puram, Balaji Nagar, New Tarachak, Danapur, Patna, Bihar 801503"
OLD = {
    "venue_address": "123 Sports Complex, Bengaluru, Karnataka 560001",
    "venue_phone": "+91 98765 43210",
    "venue_hours": "Mon–Sun: 6:00 AM – 10:00 PM",
    "whatsapp_phone": "919876543211",
}
NEW = {"venue_address": ADDRESS, "venue_phone": "+91 93153 06294", "venue_hours": "Open 24 hours", "whatsapp_phone": "919315306294"}


def test_new_databases_start_with_the_real_details(client):
    venue = {e["key"]: e["value"] for e in client.get("/api/v1/venue").json()}
    for key, value in NEW.items():
        assert venue[key] == value
    assert venue["venue_email"] == "dazyclub1223@gmail.com"  # unchanged


# ── data migration (real Alembic run on a throwaway SQLite database) ────────

def _alembic(cmd, rev, url):
    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {k: v for k, v in os.environ.items() if not k.startswith(("DAZY_", "RENDER", "R2_", "TURNSTILE"))}
    env.update({"DAZY_DB_URL": url, "PYTHONIOENCODING": "utf-8"})
    r = subprocess.run([sys.executable, "-m", "alembic", cmd, rev], cwd=api_dir, env=env, capture_output=True, text=True, timeout=240)
    assert r.returncode == 0, f"alembic {cmd} {rev} failed: {r.stdout} {r.stderr}"


def _db(url):
    return sqlite3.connect(url.removeprefix("sqlite:///"))


def _cms(url):
    con = _db(url)
    try:
        return dict(con.execute("SELECT key, value FROM cms").fetchall())
    finally:
        con.close()


def test_migration_replaces_placeholders_and_keeps_admin_edits(tmp_path):
    url = f"sqlite:///{(tmp_path / 'venue.db').as_posix()}"
    _alembic("upgrade", "q0r1s2t3u4v5", url)  # the schema before this change
    con = _db(url)
    rows = {**OLD, "venue_phone": "+91 70000 00001"}  # the admin already set a real phone number
    for k, v in rows.items():
        con.execute("INSERT INTO cms (key, label, value) VALUES (?, ?, ?)", (k, k, v))
    con.execute("INSERT INTO cms (key, label, value) VALUES ('venue_email', 'e', 'owner@example.com')")
    con.commit()
    con.close()

    _alembic("upgrade", "r1s2t3u4v5w6", url)
    cms = _cms(url)
    assert cms["venue_address"] == ADDRESS
    assert cms["venue_hours"] == "Open 24 hours"
    assert cms["whatsapp_phone"] == "919315306294"
    assert cms["venue_phone"] == "+91 70000 00001"      # edited by the admin: left alone
    assert cms["venue_email"] == "owner@example.com"    # not part of this change

    _alembic("downgrade", "q0r1s2t3u4v5", url)           # no-op: nothing is restored or lost
    assert _cms(url) == cms
    _alembic("upgrade", "r1s2t3u4v5w6", url)             # and re-applying changes nothing
    assert _cms(url) == cms


def test_migration_on_a_database_without_cms_rows_is_harmless(tmp_path):
    url = f"sqlite:///{(tmp_path / 'empty.db').as_posix()}"
    _alembic("upgrade", "r1s2t3u4v5w6", url)
    assert _cms(url) == {}


@pytest.mark.parametrize("key", list(NEW))
def test_public_venue_endpoint_exposes_the_footer_fields(client, key):
    assert key in {e["key"] for e in client.get("/api/v1/venue").json()}
