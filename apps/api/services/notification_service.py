"""Single logged entry point for outbound notifications (Detailed-Roadmap
Phase 5). Every send attempt — sent, skipped, or failed — is recorded via
notification_repo so delivery is auditable. Never raises: a notification
failure must never fail the booking (or other) flow that triggered it.
"""
from deps import booking_repo, notification_provider, whatsapp_provider, sms_provider, notification_repo
from services import notification_templates


def send_and_log(ref_type: str, ref_id: str, channel: str, to: str, subject: str, body: str, provider=None) -> None:
    if provider is None:
        provider = notification_provider
    try:
        result = provider.send(to, subject, body)
        status, detail = result.status, result.detail
    except Exception as exc:
        status, detail = "failed", str(exc)
    notification_repo.record(
        ref_type=ref_type, ref_id=ref_id, channel=channel,
        recipient=to, status=status, error_message=detail,
    )


def _send_all_channels(booking, subject: str, email_body: str, whatsapp_body: str, sms_body: str, dedup: bool = False) -> None:
    """Fire all three channels independently. Each failure is isolated.
    dedup=True skips channels that already have a 'sent' "booking" row for this booking id.
    Payment-pending notices are logged as "booking_pending" so they never suppress the confirmation."""
    if booking.email:
        if not dedup or not notification_repo.has_sent(booking.id, "email", ref_type="booking"):
            send_and_log("booking", booking.id, "email", booking.email, subject, email_body, notification_provider)
    if booking.contact and "@" not in booking.contact:
        if not dedup or not notification_repo.has_sent(booking.id, "sms", ref_type="booking"):
            send_and_log("booking", booking.id, "sms", booking.contact, subject, sms_body, sms_provider)
        if not dedup or not notification_repo.has_sent(booking.id, "whatsapp", ref_type="booking"):
            send_and_log("booking", booking.id, "whatsapp", booking.contact, subject, whatsapp_body, whatsapp_provider)


def notify_booking_confirmed(booking_ref: str) -> None:
    """Fires once per confirmed booking — callers only reach this from the
    single state transition that flips paymentStatus to "paid" (see the
    idempotency guards in routes/bookings.py and routes/payments.py)."""
    try:
        bookings = booking_repo.get_by_ref(booking_ref)
        if not bookings:
            return
        primary = next((b for b in bookings if b.is_primary), bookings[0])
        subject, email_body = notification_templates.booking_confirmation(primary)
        wa_body = notification_templates.booking_confirmation_whatsapp(primary)
        sms_body = notification_templates.booking_confirmation_sms(primary)
        _send_all_channels(primary, subject, email_body, wa_body, sms_body, dedup=True)
    except Exception:
        pass


def notify_booking_payment_pending(booking_ref: str) -> None:
    """Fires once, right after a priced booking is created — gives the
    customer a way to resume payment (via /bookings/lookup) if they close the
    tab, since there's no login/profile system to fall back on."""
    try:
        bookings = booking_repo.get_by_ref(booking_ref)
        if not bookings:
            return
        primary = next((b for b in bookings if b.is_primary), bookings[0])
        subject, body = notification_templates.booking_payment_pending(primary)
        # Payment pending only sent to email (if present) and SMS — WhatsApp reserved for confirmation.
        if primary.email:
            send_and_log("booking_pending", primary.id, "email", primary.email, subject, body, notification_provider)
        if primary.contact and "@" not in primary.contact:
            send_and_log("booking_pending", primary.id, "sms", primary.contact, subject, body, sms_provider)
    except Exception:
        pass


def notify_booking_cancelled(booking_ref: str) -> None:
    """Fires when a booking is cancelled (admin action or timeout sweep)."""
    try:
        bookings = booking_repo.get_by_ref(booking_ref)
        if not bookings:
            return
        primary = next((b for b in bookings if b.is_primary), bookings[0])
        subject, email_body = notification_templates.booking_cancelled(primary)
        sms_body = f"Booking {primary.bookingRef} cancelled. Contact us if you have questions. — {primary.sportSlug}"
        _send_all_channels(primary, subject, email_body, email_body, sms_body)
    except Exception:
        pass


def notify_booking_refunded(booking_ref: str, amount: float | None = None, cancelled: bool = True, partial: bool = False) -> None:
    """Fires when a refund is issued via the admin panel."""
    try:
        bookings = booking_repo.get_by_ref(booking_ref)
        if not bookings:
            return
        primary = next((b for b in bookings if b.is_primary), bookings[0])
        subject, email_body = notification_templates.booking_refunded(primary, amount=amount, cancelled=cancelled, partial=partial)
        shown = f"Rs. {amount:.2f} " if amount is not None else ""
        sms_body = f"Refund {shown}for booking {primary.bookingRef} is being processed. — {primary.sportSlug}"
        _send_all_channels(primary, subject, email_body, email_body, sms_body)
    except Exception:
        pass
