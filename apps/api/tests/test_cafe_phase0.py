"""
Café POS Phase 0 — backend tests.
Covers: settings CRUD, menu categories CRUD, menu items CRUD, cafe tables CRUD,
cashier PIN login, kiosk menu + tables endpoints, auth guards.
"""
import pytest
from starlette.testclient import TestClient
from main import app
from auth import hash_password
from models import UserRecord
import deps

client = TestClient(app)

ADMIN_HEADERS = {"Authorization": "Bearer " + __import__("auth").create_access_token("admin", "admin")}


def _cashier_token():
    import uuid
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    record = UserRecord(
        id=str(uuid.uuid4()),
        username="cashier1",
        hashed_password=hash_password("1234"),
        role="cashier",
        createdAt=now,
        createdBy="admin",
    )
    deps.user_repo.create(record)
    from auth import create_cashier_token
    return create_cashier_token("cashier1", "cashier")


# ── Settings ──────────────────────────────────────────────────────────────────

def test_get_settings_defaults():
    r = client.get("/api/v1/admin/cafe/settings", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    d = r.json()
    assert d["scheme"] == "regular"
    assert d["priceIncludesTax"] is True
    assert d["invoiceSeriesPrefix"] == "INV"


def test_update_settings():
    r = client.put(
        "/api/v1/admin/cafe/settings",
        json={"legalName": "Dazy Café", "scheme": "composition", "defaultTaxRate": 0},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["legalName"] == "Dazy Café"
    assert d["scheme"] == "composition"
    # Restore to regular for other tests
    client.put("/api/v1/admin/cafe/settings", json={"scheme": "regular"}, headers=ADMIN_HEADERS)


def test_settings_invalid_scheme():
    r = client.put(
        "/api/v1/admin/cafe/settings",
        json={"scheme": "bogus"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 422


def test_settings_requires_auth():
    r = client.get("/api/v1/admin/cafe/settings")
    assert r.status_code in (401, 403)


# ── Menu Categories ────────────────────────────────────────────────────────────

def test_categories_empty_on_fresh_db():
    r = client.get("/api/v1/admin/cafe/categories", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_category():
    r = client.post(
        "/api/v1/admin/cafe/categories",
        json={"name": "Hot Beverages", "kind": "beverage", "vegType": "veg", "sortOrder": 1},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 201
    d = r.json()
    assert d["name"] == "Hot Beverages"
    assert d["kind"] == "beverage"
    assert d["active"] is True


def test_create_category_invalid_kind():
    r = client.post(
        "/api/v1/admin/cafe/categories",
        json={"name": "Misc", "kind": "unknown"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 422


def test_category_appears_in_list():
    client.post(
        "/api/v1/admin/cafe/categories",
        json={"name": "Snacks", "kind": "food"},
        headers=ADMIN_HEADERS,
    )
    r = client.get("/api/v1/admin/cafe/categories", headers=ADMIN_HEADERS)
    names = [c["name"] for c in r.json()]
    assert "Snacks" in names


def test_update_category():
    create = client.post(
        "/api/v1/admin/cafe/categories",
        json={"name": "Old Name", "kind": "food"},
        headers=ADMIN_HEADERS,
    )
    cat_id = create.json()["id"]
    r = client.patch(
        f"/api/v1/admin/cafe/categories/{cat_id}",
        json={"name": "New Name"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


def test_update_category_not_found():
    r = client.patch(
        "/api/v1/admin/cafe/categories/nonexistent",
        json={"name": "X"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 404


def test_delete_category():
    create = client.post(
        "/api/v1/admin/cafe/categories",
        json={"name": "To Delete", "kind": "packaged"},
        headers=ADMIN_HEADERS,
    )
    cat_id = create.json()["id"]
    r = client.delete(f"/api/v1/admin/cafe/categories/{cat_id}", headers=ADMIN_HEADERS)
    assert r.status_code == 204
    # Deactivated — should not appear in active list
    r2 = client.get("/api/v1/admin/cafe/categories", headers=ADMIN_HEADERS)
    active_ids = [c["id"] for c in r2.json() if c["active"]]
    assert cat_id not in active_ids


def test_categories_require_auth():
    assert client.get("/api/v1/admin/cafe/categories").status_code in (401, 403)
    assert client.post("/api/v1/admin/cafe/categories", json={}).status_code in (401, 403)


# ── Menu Items ─────────────────────────────────────────────────────────────────

def _make_category(name: str = "Test Cat") -> str:
    r = client.post(
        "/api/v1/admin/cafe/categories",
        json={"name": name, "kind": "food"},
        headers=ADMIN_HEADERS,
    )
    return r.json()["id"]


def test_create_item():
    cat_id = _make_category("Mains")
    r = client.post(
        "/api/v1/admin/cafe/items",
        json={"category_id": cat_id, "name": "Paneer Wrap", "price": 180, "vegType": "veg", "station": "kitchen"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 201
    d = r.json()
    assert d["name"] == "Paneer Wrap"
    assert float(d["price"]) == 180.0
    assert d["vegType"] == "veg"


def test_create_item_invalid_station():
    cat_id = _make_category()
    r = client.post(
        "/api/v1/admin/cafe/items",
        json={"category_id": cat_id, "name": "X", "price": 50, "station": "oven"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 422


def test_item_appears_in_list():
    cat_id = _make_category("Drinks")
    client.post(
        "/api/v1/admin/cafe/items",
        json={"category_id": cat_id, "name": "Cold Coffee", "price": 120, "station": "bar"},
        headers=ADMIN_HEADERS,
    )
    r = client.get(f"/api/v1/admin/cafe/items?category_id={cat_id}", headers=ADMIN_HEADERS)
    names = [i["name"] for i in r.json()]
    assert "Cold Coffee" in names


def test_update_item():
    cat_id = _make_category()
    item = client.post(
        "/api/v1/admin/cafe/items",
        json={"category_id": cat_id, "name": "Item A", "price": 100},
        headers=ADMIN_HEADERS,
    ).json()
    r = client.patch(
        f"/api/v1/admin/cafe/items/{item['id']}",
        json={"price": 150, "available": False},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    assert float(r.json()["price"]) == 150.0
    assert r.json()["available"] is False


def test_update_item_not_found():
    r = client.patch(
        "/api/v1/admin/cafe/items/nonexistent",
        json={"price": 99},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 404


def test_delete_item():
    cat_id = _make_category()
    item = client.post(
        "/api/v1/admin/cafe/items",
        json={"category_id": cat_id, "name": "Gone Item", "price": 50},
        headers=ADMIN_HEADERS,
    ).json()
    r = client.delete(f"/api/v1/admin/cafe/items/{item['id']}", headers=ADMIN_HEADERS)
    assert r.status_code == 204


def test_items_require_auth():
    assert client.get("/api/v1/admin/cafe/items").status_code in (401, 403)


# ── Café Tables ────────────────────────────────────────────────────────────────

def test_create_table():
    r = client.post(
        "/api/v1/admin/cafe/tables",
        json={"label": "T1", "capacity": 4, "area": "Indoor"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 201
    d = r.json()
    assert d["label"] == "T1"
    assert d["status"] == "free"
    assert d["area"] == "Indoor"


def test_table_appears_in_list():
    client.post(
        "/api/v1/admin/cafe/tables",
        json={"label": "T-List", "capacity": 2},
        headers=ADMIN_HEADERS,
    )
    r = client.get("/api/v1/admin/cafe/tables", headers=ADMIN_HEADERS)
    labels = [t["label"] for t in r.json()]
    assert "T-List" in labels


def test_update_table_status():
    table = client.post(
        "/api/v1/admin/cafe/tables",
        json={"label": "T-Status", "capacity": 4},
        headers=ADMIN_HEADERS,
    ).json()
    r = client.patch(
        f"/api/v1/admin/cafe/tables/{table['id']}",
        json={"status": "occupied"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "occupied"


def test_update_table_invalid_status():
    table = client.post(
        "/api/v1/admin/cafe/tables",
        json={"label": "T-Bad", "capacity": 4},
        headers=ADMIN_HEADERS,
    ).json()
    r = client.patch(
        f"/api/v1/admin/cafe/tables/{table['id']}",
        json={"status": "broken"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 422


def test_delete_table():
    table = client.post(
        "/api/v1/admin/cafe/tables",
        json={"label": "T-Delete", "capacity": 2},
        headers=ADMIN_HEADERS,
    ).json()
    r = client.delete(f"/api/v1/admin/cafe/tables/{table['id']}", headers=ADMIN_HEADERS)
    assert r.status_code == 204


def test_tables_require_auth():
    assert client.get("/api/v1/admin/cafe/tables").status_code in (401, 403)


# ── PIN login ──────────────────────────────────────────────────────────────────

def test_cashier_pin_login():
    import uuid
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    uname = f"cashier_{uuid.uuid4().hex[:6]}"
    record = UserRecord(
        id=str(uuid.uuid4()),
        username=uname,
        hashed_password=hash_password("5678"),
        role="cashier",
        createdAt=now,
        createdBy="admin",
    )
    deps.user_repo.create(record)
    r = client.post("/api/v1/cafe/login", json={"username": uname, "pin": "5678"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_cashier_wrong_pin():
    import uuid
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    uname = f"cashier_{uuid.uuid4().hex[:6]}"
    record = UserRecord(
        id=str(uuid.uuid4()),
        username=uname,
        hashed_password=hash_password("9999"),
        role="cashier",
        createdAt=now,
        createdBy="admin",
    )
    deps.user_repo.create(record)
    r = client.post("/api/v1/cafe/login", json={"username": uname, "pin": "0000"})
    assert r.status_code == 401


def test_admin_user_cannot_use_cafe_login():
    """Admin role is not cashier/kitchen — cafe/login rejects it."""
    r = client.post("/api/v1/cafe/login", json={"username": "admin", "pin": "1234"})
    assert r.status_code == 401


# ── Kiosk endpoints (require cashier token) ────────────────────────────────────

def test_kiosk_menu_requires_auth():
    r = client.get("/api/v1/cafe/menu")
    assert r.status_code in (401, 403)


def test_kiosk_tables_requires_auth():
    r = client.get("/api/v1/cafe/tables")
    assert r.status_code in (401, 403)


def test_kiosk_menu_returns_categories_and_items():
    token = _cashier_token()
    headers = {"Authorization": f"Bearer {token}"}

    cat_id = _make_category("Kiosk Cat")
    client.post(
        "/api/v1/admin/cafe/items",
        json={"category_id": cat_id, "name": "Kiosk Item", "price": 99},
        headers=ADMIN_HEADERS,
    )

    r = client.get("/api/v1/cafe/menu", headers=headers)
    assert r.status_code == 200
    d = r.json()
    assert "categories" in d
    assert "items" in d
    names = [i["name"] for i in d["items"]]
    assert "Kiosk Item" in names


def test_kiosk_tables_endpoint():
    token = _cashier_token()
    headers = {"Authorization": f"Bearer {token}"}
    client.post(
        "/api/v1/admin/cafe/tables",
        json={"label": "KT1", "capacity": 4},
        headers=ADMIN_HEADERS,
    )
    r = client.get("/api/v1/cafe/tables", headers=headers)
    assert r.status_code == 200
    labels = [t["label"] for t in r.json()]
    assert "KT1" in labels
