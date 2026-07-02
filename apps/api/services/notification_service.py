"""Single logged entry point for outbound notifications (Detailed-Roadmap
Phase 5). Every send attempt — sent, skipped, or failed — is recorded via
notification_repo so delivery is auditable. Never raises: a notification
failure must never fail the booking (or other) flow that triggered it.
"""
from deps import booking_repo, notification_provider, notification_repo
from services import notification_templates


def send_and_log(ref_type: str, ref_id: str, to: str, subject: str, body: str) -> None:
    channel = "email" if "@" in to else "sms"
    try:
        result = notification_provider.send(to, subject, body)
        status, detail = result.status, result.detail
    except Exception as exc:
        status, detail = "failed", str(exc)
    notification_repo.record(
        ref_type=ref_type, ref_id=ref_id, channel=channel,
        recipient=to, status=status, error_message=detail,
    )


def notify_booking_confirmed(booking_ref: str) -> None:
    """Fires once per confirmed booking — callers only reach this from the
    single state transition that flips paymentStatus to "paid" (see the
    idempotency guards in routes/bookings.py and routes/payments.py)."""
    try:
        bookings = booking_repo.get_by_ref(booking_ref)
        if not bookings:
            return
        primary = next((b for b in bookings if b.is_primary), bookings[0])
        subject, body = notification_templates.booking_confirmation(primary)
        send_and_log("booking", primary.id, primary.contact, subject, body)
    except Exception:
        pass
