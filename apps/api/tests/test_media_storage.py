"""Media storage backends (local disk and Cloudflare R2) and the gallery upload/delete routes.
R2 is exercised against an in-memory fake of the S3 client, never the network."""
import os

import pytest

import media_store
from media_store import LocalStorage, R2Storage

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
BASE = "https://media.example.com"


class FakeS3:
    def __init__(self, fail_put=False, fail_delete=False):
        self.objects: dict[str, dict] = {}
        self.fail_put, self.fail_delete = fail_put, fail_delete
        self.deleted: list[str] = []

    def put_object(self, Bucket, Key, Body, ContentType, CacheControl):
        if self.fail_put:
            raise RuntimeError("R2 unavailable")
        self.objects[Key] = {"bucket": Bucket, "body": Body, "type": ContentType, "cache": CacheControl}

    def delete_object(self, Bucket, Key):
        if self.fail_delete:
            raise RuntimeError("R2 unavailable")
        self.deleted.append(Key)
        self.objects.pop(Key, None)


@pytest.fixture(autouse=True)
def _fresh_storage():
    media_store.reset_storage()
    yield
    media_store.reset_storage()


def _use(monkeypatch, storage):
    monkeypatch.setattr(media_store, "_storage", storage)


# ── R2Storage unit behaviour ────────────────────────────────────────────────

def test_r2_save_returns_public_url_and_sets_headers():
    fake = FakeS3()
    url = R2Storage("bucket", BASE + "/", fake).save("abc.png", PNG, ".png")
    assert url == f"{BASE}/gallery/abc.png"
    obj = fake.objects["gallery/abc.png"]
    assert obj["bucket"] == "bucket" and obj["body"] == PNG and obj["type"] == "image/png"
    assert "immutable" in obj["cache"]


@pytest.mark.parametrize("ext,ctype", [(".jpg", "image/jpeg"), (".webp", "image/webp"), (".gif", "image/gif")])
def test_r2_content_types(ext, ctype):
    fake = FakeS3()
    R2Storage("b", BASE, fake).save(f"x{ext}", b"data", ext)
    assert fake.objects[f"gallery/x{ext}"]["type"] == ctype


def test_r2_delete_only_touches_our_gallery_keys():
    fake = FakeS3()
    r2 = R2Storage("b", BASE, fake)
    r2.delete(f"{BASE}/gallery/abc.png")
    r2.delete("https://example.com/e2e-cricket.jpg")        # external image
    r2.delete("/media/gallery/legacy.png")                   # legacy local path
    r2.delete(f"{BASE}/other/secret.png")                    # same host, not a gallery key
    r2.delete(None)
    assert fake.deleted == ["gallery/abc.png"]


def test_r2_delete_failure_is_swallowed():
    R2Storage("b", BASE, FakeS3(fail_delete=True)).delete(f"{BASE}/gallery/abc.png")  # must not raise


# ── backend selection ───────────────────────────────────────────────────────

def test_default_backend_is_local(monkeypatch):
    monkeypatch.delenv("DAZY_MEDIA_BACKEND", raising=False)
    assert media_store.get_storage().name == "local"


def test_unknown_backend_rejected(monkeypatch):
    monkeypatch.setenv("DAZY_MEDIA_BACKEND", "ftp")
    with pytest.raises(RuntimeError, match="Unknown DAZY_MEDIA_BACKEND"):
        media_store.get_storage()


def test_r2_backend_needs_all_settings(monkeypatch):
    monkeypatch.setenv("DAZY_MEDIA_BACKEND", "r2")
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_PUBLIC_BASE_URL"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(RuntimeError, match="R2_ACCOUNT_ID"):
        media_store.get_storage()


def test_r2_from_env_builds_a_signed_s3_client(monkeypatch):
    monkeypatch.setenv("DAZY_MEDIA_BACKEND", "r2")
    for k, v in {"R2_ACCOUNT_ID": "acct123", "R2_ACCESS_KEY_ID": "key", "R2_SECRET_ACCESS_KEY": "secret",
                 "R2_BUCKET": "dazy", "R2_PUBLIC_BASE_URL": BASE}.items():
        monkeypatch.setenv(k, v)
    st = media_store.get_storage()
    assert st.name == "r2"
    assert st._client.meta.endpoint_url == "https://acct123.r2.cloudflarestorage.com"
    assert st._bucket == "dazy"


# ── LocalStorage ────────────────────────────────────────────────────────────

def test_local_save_and_delete_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr(media_store, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(media_store, "MEDIA_GALLERY_DIR", str(tmp_path / "gallery"))
    url = LocalStorage().save("one.png", PNG, ".png")
    assert url == "/media/gallery/one.png" and (tmp_path / "gallery" / "one.png").read_bytes() == PNG
    LocalStorage().delete(url)
    assert not (tmp_path / "gallery" / "one.png").exists()
    LocalStorage().delete("https://example.com/x.png")  # external: ignored


# ── routes ──────────────────────────────────────────────────────────────────

def _upload(client, auth_headers, name="shot.png", content=PNG):
    return client.post("/api/v1/admin/gallery/upload", headers=auth_headers, files={"file": (name, content, "image/png")})


def test_upload_goes_to_r2_when_configured(client, auth_headers, monkeypatch):
    fake = FakeS3()
    _use(monkeypatch, R2Storage("bucket", BASE, fake))
    r = _upload(client, auth_headers)
    assert r.status_code == 200
    url = r.json()["imageUrl"]
    assert url.startswith(f"{BASE}/gallery/") and url.endswith(".png")
    assert list(fake.objects) == [url[len(BASE) + 1:]]


def test_upload_validation_runs_before_any_storage_call(client, auth_headers, monkeypatch):
    fake = FakeS3()
    _use(monkeypatch, R2Storage("bucket", BASE, fake))
    assert _upload(client, auth_headers, name="evil.exe").status_code == 400
    assert _upload(client, auth_headers, name="fake.png", content=b"not an image").status_code == 400
    assert fake.objects == {}


def test_upload_storage_outage_returns_502_not_500(client, auth_headers, monkeypatch):
    _use(monkeypatch, R2Storage("bucket", BASE, FakeS3(fail_put=True)))
    r = _upload(client, auth_headers)
    assert r.status_code == 502 and "try again" in r.json()["detail"].lower()


def test_upload_requires_admin(client):
    assert client.post("/api/v1/admin/gallery/upload", files={"file": ("a.png", PNG, "image/png")}).status_code in (401, 403)


def test_deleting_item_removes_its_r2_object(client, auth_headers, monkeypatch):
    fake = FakeS3()
    _use(monkeypatch, R2Storage("bucket", BASE, fake))
    url = _upload(client, auth_headers).json()["imageUrl"]
    item = client.post("/api/v1/admin/gallery", headers=auth_headers,
                       json={"title": "Court", "sportSlug": "cricket", "tone": "gold", "imageUrl": url, "approved": True})
    assert item.status_code == 201, item.text
    assert client.delete(f"/api/v1/admin/gallery/{item.json()['id']}", headers=auth_headers).status_code == 204
    assert fake.deleted == [url[len(BASE) + 1:]] and fake.objects == {}


def test_deleting_item_with_legacy_local_url_still_cleans_disk(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setattr(media_store, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(media_store, "MEDIA_GALLERY_DIR", str(tmp_path / "gallery"))
    os.makedirs(tmp_path / "gallery")
    (tmp_path / "gallery" / "old.png").write_bytes(PNG)
    _use(monkeypatch, R2Storage("bucket", BASE, FakeS3()))  # switched to R2 after this row was uploaded
    item = client.post("/api/v1/admin/gallery", headers=auth_headers,
                       json={"title": "Old", "sportSlug": "cricket", "tone": "gold",
                             "imageUrl": "/media/gallery/old.png", "approved": True}).json()
    assert client.delete(f"/api/v1/admin/gallery/{item['id']}", headers=auth_headers).status_code == 204
    assert not (tmp_path / "gallery" / "old.png").exists()


def test_deleting_item_with_external_url_touches_nothing(client, auth_headers, monkeypatch):
    fake = FakeS3()
    _use(monkeypatch, R2Storage("bucket", BASE, fake))
    items = client.get("/api/v1/admin/gallery", headers=auth_headers).json()
    assert client.delete(f"/api/v1/admin/gallery/{items[0]['id']}", headers=auth_headers).status_code == 204
    assert fake.deleted == []
