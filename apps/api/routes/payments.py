"""Payment gateway webhooks — the source of truth for payment confirmation
(the client-side /bookings/{ref}/payment/verify callback is a UX shortcut;
this is what actually must be trusted, since a client can go offline right
after paying). Public by nature (gateways can't send bearer tokens) — trust
is established via signature verification instead, not auth."""
from fastapi import APIRouter, HTTPException, Request

from deps import booking_payment_repo, booking_repo, payment_provider
from services.notification_service import notify_booking_confirmed

router = APIRouter()


@router.post("/payments/razorpay/webhook")
async def razorpay_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    verification, provider_order_id = payment_provider.verify_webhook(raw_body, signature)
    if not verification.verified or not provider_order_id:
        raise HTTPException(status_code=400, detail=verification.reason or "Webhook verification failed.")

    payment = booking_payment_repo.get_by_order_id(provider_order_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Unknown order.")

    # Idempotent — a gateway may redeliver the same webhook.
    if payment.status != "verified":
        booking_payment_repo.mark_verified(provider_order_id, verification.providerPaymentId, signature)
        booking_repo.confirm_payment_by_ref(payment.bookingRef)
        notify_booking_confirmed(payment.bookingRef)
    return {"status": "ok"}
