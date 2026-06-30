"""Local media storage paths. Uploaded gallery images live under media/gallery/
and are served read-only at /media (mounted in main.py). Stored in DB as the
relative path /media/gallery/<uuid>.<ext> so a future shift to a CDN/URL-only
model only needs the served prefix to change.
"""
import os

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIR = os.path.join(_BASE_DIR, "media")
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
