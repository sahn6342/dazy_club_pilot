"""One-time codes proving a customer controls an email address or phone (WhatsApp).

Used to gate contact-only booking search, which would otherwise let anyone who knows a
phone number or email list that person's bookings. Codes are 6 digits, valid 10 minutes,
single use, max 5 wrong guesses, and stored only as an HMAC (never in plaintext)."""
import hashlib
import hmac
import logging
import os
import re
import secrets
import time
import uuid

from sqlalchemy import delete, select

import auth
from db import _session
from db_models import OtpCodeRow
from deps import notification_provider, whatsapp_provider, notification_repo

logger = logging.getLogger(__name__)

OTP_TTL_SECONDS = 600
MAX_ATTEMPTS = 5

_PHONE_RE = re.compile(r"^\d{10}$")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")


def otp_disabled() -> bool:
    """Explicit opt-out (DAZY_OTP_DISABLED=1): GET /bookings/search then lists every booking for a phone or email
    with no code, so anyone who knows a contact can see its bookings. For use while no email/WhatsApp/SMS delivery
    exists to carry the code. Remove the variable to require the code again."""
    return os.environ.get("DAZY_OTP_DISABLED", "").strip().lower() in ("1", "true", "yes", "on")


def normalize_contact(contact: str) -> str:
    return contact.strip().lower()


def validate_contact(contact: str) -> str | None:
    """Return an error message, or None if `contact` is a valid email / 10-digit mobile."""
    c = normalize_contact(contact)
    if not _PHONE_RE.match(c) and not _EMAIL_RE.match(c):
        return "Enter a valid 10-digit mobile number or email address."
    return None


def _hash(contact: str, code: str) -> str:
    return hmac.new(auth._SECRET.encode(), f"{contact}|{code}".encode(), hashlib.sha256).hexdigest()


def request_otp(contact: str) -> str:
    """Create and send a code. Returns the channel used ("email" | "whatsapp").
    Delivery problems are logged but not surfaced: the response must not reveal anything."""
    contact = normalize_contact(contact)
    code = f"{secrets.randbelow(10**6):06d}"
    now = time.time()
    with _session() as s:
        s.execute(delete(OtpCodeRow).where(OtpCodeRow.contact == contact))  # newest code wins
        s.add(OtpCodeRow(id=str(uuid.uuid4()), contact=contact, code_hash=_hash(contact, code),
                         expires_at=now + OTP_TTL_SECONDS, attempts=0, created_at=now))
    channel = "email" if "@" in contact else "whatsapp"
    provider = notification_provider if channel == "email" else whatsapp_provider
    try:
        result = provider.send_otp(contact, code)
        status, detail = result.status, result.detail
    except Exception as exc:
        status, detail = "failed", str(exc)
    if status != "sent":
        logger.error("OTP delivery %s via %s: %s", status, channel, detail)
    # The code itself is never logged or stored; only delivery metadata.
    notification_repo.record(ref_type="otp", ref_id=hashlib.sha256(contact.encode()).hexdigest()[:16],
                             channel=channel, recipient=contact, status=status, error_message=detail)
    return channel


def verify_otp(contact: str, code: str) -> bool:
    """True (and burns the code) when `code` matches the live code for `contact`."""
    contact = normalize_contact(contact)
    now = time.time()
    with _session() as s:
        row = s.scalar(select(OtpCodeRow).where(OtpCodeRow.contact == contact))
        if row is None or row.expires_at < now or row.attempts >= MAX_ATTEMPTS:
            return False
        if hmac.compare_digest(row.code_hash, _hash(contact, code.strip())):
            s.delete(row)
            return True
        row.attempts += 1
        return False
