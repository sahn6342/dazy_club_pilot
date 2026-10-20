"""Media storage for admin uploads (gallery images).

Two backends, chosen by DAZY_MEDIA_BACKEND:
  local (default)  files under DAZY_MEDIA_DIR/gallery, served read-only at /media (main.py);
                   stored in the DB as /media/gallery/<uuid>.<ext>. Lost on redeploy unless a
                   persistent disk is mounted, so production uses r2.
  r2               Cloudflare R2 (S3 API). Objects are public under R2_PUBLIC_BASE_URL; the full
                   public URL is what gets stored in the DB. If that base URL ever changes,
                   rewrite the stored prefix with one SQL UPDATE on gallery.imageUrl.
Validation (extension, size, magic bytes) happens in the route before any backend is called.
"""
import logging
import os

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_MEDIA_DIR = os.path.join(_BASE_DIR, "media")
MEDIA_DIR = os.environ.get("DAZY_MEDIA_DIR", _DEFAULT_MEDIA_DIR)
MEDIA_GALLERY_DIR = os.path.join(MEDIA_DIR, "gallery")

ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

# Magic byte signatures for allowed image types.
# WEBP: RIFF header + 4-byte size + "WEBP" at offset 8.
_MAGIC: list[tuple[bytes, set[str]]] = [
    (b"\xff\xd8\xff", {".jpg", ".jpeg"}),
    (b"\x89PNG\r\n\x1a\n", {".png"}),
    (b"GIF87a", {".gif"}),
    (b"GIF89a", {".gif"}),
]


def validate_magic_bytes(content: bytes, ext: str) -> bool:
    """Return True if content's magic bytes are consistent with ext."""
    # WEBP is RIFF....WEBP — check both signatures.
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ext == ".webp"
    for magic, allowed_exts in _MAGIC:
        if content[: len(magic)] == magic:
            return ext in allowed_exts
    return False


def ensure_media_dirs() -> None:
    os.makedirs(MEDIA_GALLERY_DIR, exist_ok=True)


def local_path_for(image_url: str | None) -> str | None:
    """Map a stored /media/... URL back to an on-disk path, or None if it's
    an external URL (or empty)."""
    if not image_url or not image_url.startswith("/media/"):
        return None
    rel = image_url[len("/media/"):]
    return os.path.join(MEDIA_DIR, *rel.split("/"))


# ── Storage backends ────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

_CONTENT_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                  ".webp": "image/webp", ".gif": "image/gif"}
_R2_KEY_PREFIX = "gallery/"


class LocalStorage:
    name = "local"

    def save(self, name: str, content: bytes, ext: str) -> str:
        ensure_media_dirs()
        with open(os.path.join(MEDIA_GALLERY_DIR, name), "wb") as out:
            out.write(content)
        return f"/media/gallery/{name}"

    def delete(self, image_url: str | None) -> None:
        path = local_path_for(image_url)
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                logger.warning("Could not remove local media file %s", path)


class R2Storage:
    """Cloudflare R2 through boto3's S3 client. `client` can be injected (tests)."""
    name = "r2"

    def __init__(self, bucket: str, public_base_url: str, client=None):
        self._bucket = bucket
        self._base = public_base_url.rstrip("/")
        self._client = client

    @classmethod
    def from_env(cls) -> "R2Storage":
        missing = [k for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_PUBLIC_BASE_URL")
                   if not os.environ.get(k)]
        if missing:
            raise RuntimeError(f"DAZY_MEDIA_BACKEND=r2 needs {', '.join(missing)}.")
        import boto3  # lazy: local-only deployments never import it
        from botocore.config import Config
        client = boto3.client(
            "s3",
            endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}, connect_timeout=5, read_timeout=15),
        )
        return cls(os.environ["R2_BUCKET"], os.environ["R2_PUBLIC_BASE_URL"], client)

    def save(self, name: str, content: bytes, ext: str) -> str:
        key = f"{_R2_KEY_PREFIX}{name}"
        self._client.put_object(
            Bucket=self._bucket, Key=key, Body=content,
            ContentType=_CONTENT_TYPES.get(ext, "application/octet-stream"),
            CacheControl="public, max-age=31536000, immutable",  # names are uuids, never overwritten
        )
        return f"{self._base}/{key}"

    def _key_for(self, image_url: str | None) -> str | None:
        if not image_url or not image_url.startswith(self._base + "/"):
            return None  # external URL or a legacy /media/ path: not ours to delete here
        key = image_url[len(self._base) + 1:]
        return key if key.startswith(_R2_KEY_PREFIX) else None

    def delete(self, image_url: str | None) -> None:
        key = self._key_for(image_url)
        if not key:
            return
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except Exception:
            logger.exception("R2 delete failed for %s", key)  # best effort; the DB row is already gone


_storage = None


def media_backend() -> str:
    return os.environ.get("DAZY_MEDIA_BACKEND", "local").strip().lower()


def get_storage():
    """Process-wide storage backend (built lazily so tests/env changes can reset it)."""
    global _storage
    if _storage is None:
        backend = media_backend()
        if backend == "r2":
            _storage = R2Storage.from_env()
        elif backend == "local":
            _storage = LocalStorage()
        else:
            raise RuntimeError(f"Unknown DAZY_MEDIA_BACKEND '{backend}' (use 'local' or 'r2').")
    return _storage


def reset_storage() -> None:
    global _storage
    _storage = None
