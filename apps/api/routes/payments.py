"""Payment gateway webhooks — the source of truth for payment confirmation
(the client-side /bookings/{ref}/payment/verify callback is a UX shortcut;
this is what actually must be trusted, since a client can go offline right
after paying). Public by nature (gateways can't send bearer tokens) — trust
is established via signature verification instead, not auth."""
from fastapi import APIRouter, HTTPException, Request

from deps import booking_payment_repo, payment_provider
from services.payment_confirmation import confirm_verified_payment

router = APIRouter()


@router.post("/payments/razorpay/webhook")
async def razorpay_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    verification, provider_order_id = payment_provider.verify_webhook(raw_body, signature)
    if not verification.verified:
        # Unrecognised event type: signature is valid but we don't handle this event.
        # Returning 200 silences Razorpay retries for non-payment events.
        if verification.reason == "unrecognised_event":
            return {"status": "ignored"}
        raise HTTPException(status_code=400, detail=verification.reason or "Webhook verification failed.")
    if not provider_order_id:
        raise HTTPException(status_code=400, detail="Webhook verification failed.")

    payment = booking_payment_repo.get_by_order_id(provider_order_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Unknown order.")

    # Idempotent and race-safe: late payments are refunded/flagged, never resurrect a booking.
    # Always 200 once the signature checked out, so the gateway stops redelivering.
    result = confirm_verified_payment(
        payment.bookingRef, provider_order_id, verification.providerPaymentId, signature
    )
    return {"status": "ok" if result.booking_confirmed else result.outcome}
