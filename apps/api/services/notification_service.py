"""Single logged entry point for outbound notifications. Every message is written to the outbox
(`notification_messages`) BEFORE the provider is called and updated with the outcome, so delivery is
auditable and a failed message can be sent again.

Failure handling:
  * a permanent failure (rejected number, missing configuration, refused template) is final: status "failed";
  * a transient one (timeout, 5xx, rate limit, provider outage) is retried after 2 min and again after 10 min
    (3 attempts in total) by the scheduler (POST /internal/sweep -> retry_due_notifications), then it is "failed";
  * a retry is dropped as "skipped" if it stopped being true (a payment reminder for a booking that has since
    been paid or cancelled, a confirmation for one that was cancelled) or is more than 24 h old;
  * an admin can resend any failed/skipped row by hand from the notification log.
Nothing here ever raises: a notification problem must never fail the booking flow that triggered it. OTP codes
are NOT stored or retried (see services/otp_service.py): the customer simply asks for a new code."""
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from deps import booking_repo, notification_provider, whatsapp_provider, sms_provider, notification_repo
from integrations.notifications.base import NotificationResult
from services import notification_templates

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
RETRY_DELAYS = [timedelta(minutes=2), timedelta(minutes=10)]  # wait after attempt 1, after attempt 2
MAX_AGE = timedelta(hours=24)
STUCK_AFTER = timedelta(minutes=10)

_STUB_PROVIDERS = {"console", "sms_stub", "whatsapp_stub"}


@dataclass
class Message:
    """One lifecycle notification, rendered for every channel."""
    event: str
    subject: str
    email_body: str
    sms_body: str
    whatsapp_body: str
    params: list[str] = field(default_factory=list)  # fill the numbered variables of the SMS/WhatsApp templates


def _providers() -> dict:
    # Looked up on every call (not cached) so tests and hot config changes can swap them.
    return {"email": notification_provider, "sms": sms_provider, "whatsapp": whatsapp_provider}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _deliver(channel: str, to: str, event: str, payload: dict, provider=None) -> NotificationResult:
    provider = provider or _providers()[channel]
    try:
        if channel == "email":
            return provider.send(to, payload["subject"], payload["body"])
        return provider.send_template(to, event, payload.get("params", []), payload["subject"], payload["body"])
    except Exception as exc:  # a provider bug or network error: treat as transient, the retry decides
        logger.exception("Notification provider %s raised", getattr(provider, "name", channel))
        return NotificationResult(status="failed", detail=str(exc), retryable=True)


def _settle(row_id: str, attempts: int, result: NotificationResult, allow_retry: bool = True) -> str:
    """Write the outcome of one attempt and return the final/queued status."""
    if result.status == "sent":
        notification_repo.finish_attempt(row_id, "sent", provider_ref=result.detail)
        return "sent"
    if result.status == "skipped":
        notification_repo.finish_attempt(row_id, "skipped", result.detail)
        return "skipped"
    if allow_retry and result.retryable and attempts < MAX_ATTEMPTS:
        when = (_now() + RETRY_DELAYS[min(attempts, len(RETRY_DELAYS)) - 1]).isoformat()
        notification_repo.finish_attempt(row_id, "retrying", result.detail, next_attempt_at=when)
        logger.warning("Notification %s failed (attempt %s/%s), will retry: %s", row_id, attempts, MAX_ATTEMPTS, result.detail)
        return "retrying"
    notification_repo.finish_attempt(row_id, "failed", result.detail)
    logger.error("Notification %s failed for good after %s attempt(s): %s", row_id, attempts, result.detail)
    return "failed"


def send_and_log(
    ref_type: str, ref_id: str, channel: str, to: str, subject: str, body: str, provider=None,
    event: str = "generic", params: list[str] | None = None,
) -> str:
    """Send one message on one channel through the outbox. Returns the resulting status. Never raises."""
    payload = {"subject": subject, "body": body, "params": params or []}
    try:
        row_id = notification_repo.create_attempt(
            ref_type, ref_id, channel, to, event, json.dumps(payload),
            getattr(provider or _providers()[channel], "name", channel))
        return _settle(row_id, 1, _deliver(channel, to, event, payload, provider))
    except Exception:
        logger.exception("Could not record or send %s notification for %s", channel, ref_id)
        return "failed"


def _send_all_channels(booking, msg: Message, dedup: bool = False, ref_type: str = "booking", whatsapp: bool = True) -> None:
    """Email (if the booking has an address) and, for phone contacts, SMS and WhatsApp. Each channel is
    independent. dedup=True skips channels that already delivered this "booking" event.
    Payment-pending notices use ref_type "booking_pending" so they never suppress the confirmation."""
    def send(channel: str, to: str):
        if dedup and notification_repo.has_sent(booking.id, channel, ref_type=ref_type):
            return
        send_and_log(ref_type, booking.id, channel, to, msg.subject, _payload_body(msg, channel), event=msg.event, params=msg.params)

    if booking.email:
        send("email", booking.email)
    if booking.contact and "@" not in booking.contact:
        send("sms", booking.contact)
        if whatsapp:
            send("whatsapp", booking.contact)


def _payload_body(msg: Message, channel: str) -> str:
    return {"email": msg.email_body, "sms": msg.sms_body, "whatsapp": msg.whatsapp_body}[channel]


def _primary(booking_ref: str):
    bookings = booking_repo.get_by_ref(booking_ref, include_deleted=True)
    if not bookings:
        return None
    return next((b for b in bookings if b.is_primary), bookings[0])


def notify_booking_confirmed(booking_ref: str) -> None:
    """Fires once per confirmed booking: callers only reach this from the single state transition that
    flips paymentStatus to "paid" (see the idempotency guards in routes/bookings.py and routes/payments.py)."""
    try:
        b = _primary(booking_ref)
        if not b:
            return
        subject, email_body = notification_templates.booking_confirmation(b)
        msg = Message("booking_confirmed", subject, email_body, notification_templates.booking_confirmation_sms(b),
                      notification_templates.booking_confirmation_whatsapp(b),
                      notification_templates.template_params("booking_confirmed", b))
        _send_all_channels(b, msg, dedup=True)
    except Exception:
        logger.exception("notify_booking_confirmed failed for %s", booking_ref)


def notify_booking_payment_pending(booking_ref: str) -> None:
    """Fires once, right after a priced booking is created: gives the customer a way to resume payment
    (via /bookings/lookup) if they close the tab. Email and SMS only; WhatsApp is kept for confirmations."""
    try:
        b = _primary(booking_ref)
        if not b:
            return
        subject, body = notification_templates.booking_payment_pending(b)
        msg = Message("booking_pending", subject, body, body, body, notification_templates.template_params("booking_pending", b))
        _send_all_channels(b, msg, ref_type="booking_pending", whatsapp=False)
    except Exception:
        logger.exception("notify_booking_payment_pending failed for %s", booking_ref)


def notify_booking_cancelled(booking_ref: str) -> None:
    """Fires when a booking is cancelled (admin action or timeout sweep)."""
    try:
        b = _primary(booking_ref)
        if not b:
            return
        subject, email_body = notification_templates.booking_cancelled(b)
        sms_body = f"Booking {b.bookingRef} cancelled. Contact us if you have questions. — {b.sportSlug}"
        msg = Message("booking_cancelled", subject, email_body, sms_body, email_body,
                      notification_templates.template_params("booking_cancelled", b))
        _send_all_channels(b, msg)
    except Exception:
        logger.exception("notify_booking_cancelled failed for %s", booking_ref)


def notify_booking_refunded(booking_ref: str, amount: float | None = None, cancelled: bool = True, partial: bool = False) -> None:
    """Fires when a refund is issued via the admin panel."""
    try:
        b = _primary(booking_ref)
        if not b:
            return
        subject, email_body = notification_templates.booking_refunded(b, amount=amount, cancelled=cancelled, partial=partial)
        shown = f"Rs. {amount:.2f} " if amount is not None else ""
        sms_body = f"Refund {shown}for booking {b.bookingRef} is being processed. — {b.sportSlug}"
        msg = Message("booking_refunded", subject, email_body, sms_body, email_body,
                      notification_templates.template_params("booking_refunded", b, amount=amount, cancelled=cancelled))
        _send_all_channels(b, msg)
    except Exception:
        logger.exception("notify_booking_refunded failed for %s", booking_ref)


# ── retries ──────────────────────────────────────────────────────────────────

def _still_relevant(event: str, booking_id: str) -> tuple[bool, str]:
    """Would sending this message now still be true? Returns (ok, why-not)."""
    if event == "booking_refunded":
        return True, ""
    booking = booking_repo.get_by_id(booking_id)
    if booking is None:
        return False, "booking no longer exists"
    status = booking.status
    if event == "booking_pending":
        return (status == "pending" and not booking.deleted_at, f"booking is {status}")
    if event == "booking_confirmed":
        return (status in ("confirmed", "completed"), f"booking is {status}")
    if event == "booking_cancelled":
        return (status == "cancelled", f"booking is {status}")
    return True, ""


def _run_claimed(dto, payload_json: str, *, check_relevance: bool, allow_retry: bool) -> str:
    """Make one more attempt for a row that has already been claimed (status 'sending')."""
    try:
        age = _now() - datetime.fromisoformat(dto.createdAt)
        if check_relevance and age > MAX_AGE:
            notification_repo.finish_attempt(dto.id, "failed", "gave up: older than 24 h")
            return "failed"
        if check_relevance:
            ok, why = _still_relevant(dto.event or "", dto.refId)
            if not ok:
                notification_repo.finish_attempt(dto.id, "skipped", f"no longer relevant ({why})")
                return "skipped"
        result = _deliver(dto.channel, dto.recipient, dto.event or "generic", json.loads(payload_json))
        return _settle(dto.id, dto.attempts, result, allow_retry=allow_retry)
    except Exception:
        logger.exception("Retrying notification %s crashed", dto.id)
        notification_repo.finish_attempt(dto.id, "failed", "internal error while retrying")
        return "failed"


def retry_due_notifications(limit: int = 50) -> dict:
    """Called by the scheduler. Re-queues messages orphaned by a crash, then sends every retry that is due."""
    summary = {"rescued": 0, "attempted": 0, "sent": 0, "retrying": 0, "failed": 0, "skipped": 0}
    try:
        now = _now()
        summary["rescued"] = notification_repo.rescue_stuck((now - STUCK_AFTER).isoformat())
        for dto in notification_repo.claim_due(now.isoformat(), limit):
            found = notification_repo.get(dto.id)
            if not found:
                continue
            outcome = _run_claimed(dto, found[1], check_relevance=True, allow_retry=True)
            summary["attempted"] += 1
            summary[outcome] += 1
    except Exception:
        logger.exception("retry_due_notifications failed")
    return summary


def resend(row_id: str) -> tuple[str, object] | None:
    """Manual resend from the admin log. One immediate attempt; a failure is reported as final (the admin
    is looking at it) rather than queued. Returns (outcome, updated row) or None if the row cannot be resent."""
    if not notification_repo.claim_for_resend(row_id):
        return None
    found = notification_repo.get(row_id)
    if not found:
        return None
    outcome = _run_claimed(found[0], found[1], check_relevance=False, allow_retry=False)
    return outcome, notification_repo.get(row_id)[0]


# ── what is actually configured, for startup warnings and /health/ready ──────

def delivery_status() -> dict:
    names = {ch: getattr(p, "name", "unknown") for ch, p in _providers().items()}
    production = os.environ.get("DAZY_ENV", "").lower() == "production" or bool(os.environ.get("RENDER"))
    warnings = []
    if production:
        if names["email"] in _STUB_PROVIDERS:
            warnings.append("Email is on the console provider: no customer receives emails (set DAZY_NOTIFY_PROVIDER=email).")
        if names["sms"] in _STUB_PROVIDERS:
            warnings.append("SMS is on a stub: phone-number customers get no SMS (set DAZY_NOTIFY_SMS_PROVIDER=msg91).")
        if names["whatsapp"] in _STUB_PROVIDERS:
            warnings.append("WhatsApp is on a stub: phone-number customers get no WhatsApp and no OTP codes "
                            "(set DAZY_NOTIFY_WHATSAPP_PROVIDER=whatsapp_cloud).")
    counts = notification_repo.counts_by_status()
    return {"providers": names, "warnings": warnings,
            "queue": {"retrying": counts.get("retrying", 0), "sending": counts.get("sending", 0)}}
