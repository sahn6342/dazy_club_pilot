"""Dev/test payment provider — no real gateway. Lets the whole booking-payment
flow (create -> checkout -> verify -> confirm) be exercised end-to-end without
Razorpay credentials. Never select this in production (see factory.py)."""
import json
import uuid

from .base import PaymentProvider, PaymentOrder, PaymentVerification


class NoopPaymentProvider(PaymentProvider):
    name = "noop"

    def create_order(self, amount: float, ref: str) -> PaymentOrder:
        order_id = f"noop_order_{uuid.uuid4().hex[:12]}"
        return PaymentOrder(
            provider=self.name, providerOrderId=order_id, amount=amount, currency="INR",
            checkout={"provider": "noop", "providerOrderId": order_id, "amount": amount, "currency": "INR"},
        )

    def verify_payment(self, provider_order_id: str, provider_payment_id: str, signature: str | None) -> PaymentVerification:
        # Nothing to check against — dev mode trusts the client-reported payment id outright.
        return PaymentVerification(verified=True, providerPaymentId=provider_payment_id or f"noop_pay_{uuid.uuid4().hex[:12]}")

    def verify_webhook(self, raw_body: bytes, signature: str | None) -> tuple[PaymentVerification, str | None]:
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return PaymentVerification(verified=False, reason="Invalid payload."), None
        order_id = payload.get("providerOrderId")
        payment_id = payload.get("providerPaymentId") or f"noop_pay_{uuid.uuid4().hex[:12]}"
        return PaymentVerification(verified=True, providerPaymentId=payment_id), order_id

    def refund(self, provider_payment_id: str, amount: float) -> bool:
        return True
