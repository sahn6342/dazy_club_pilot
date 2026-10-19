"""Real Razorpay integration. Uses stdlib urllib (no SDK dependency) since the
REST surface needed here (create order, refund) is small. Requires
RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET; RAZORPAY_WEBHOOK_SECRET for webhooks.
Selected via DAZY_PAYMENT_PROVIDER=razorpay (see factory.py) — never imported
unless that env var is set, so a noop-only deployment needs none of this."""
import base64
import hashlib
import hmac
import json
import logging
import os
import urllib.error
import urllib.request

from .base import PaymentProvider, PaymentOrder, PaymentVerification, CapturedPayment

_API = "https://api.razorpay.com/v1"
_SUPPORTED_EVENTS = {"payment.captured"}
_IGNORED_BUT_LOGGED = {"payment.failed"}

logger = logging.getLogger(__name__)


class RazorpayPaymentProvider(PaymentProvider):
    name = "razorpay"

    def __init__(self):
        self._key_id = os.environ["RAZORPAY_KEY_ID"]
        self._key_secret = os.environ["RAZORPAY_KEY_SECRET"]
        self._webhook_secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
        if not self._webhook_secret:
            logger.warning("RAZORPAY_WEBHOOK_SECRET not set — webhooks will be rejected.")

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{_API}{path}", data=data, method=method)
        token = base64.b64encode(f"{self._key_id}:{self._key_secret}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Razorpay API error {e.code}: {e.read().decode()}")

    def create_order(self, amount: float, ref: str) -> PaymentOrder:
        paise = int(round(amount * 100))  # Razorpay amounts are integer paise.
        order = self._request("POST", "/orders", {"amount": paise, "currency": "INR", "receipt": ref})
        return PaymentOrder(
            provider=self.name, providerOrderId=order["id"], amount=amount, currency="INR",
            checkout={"provider": "razorpay", "key": self._key_id, "order_id": order["id"], "amount": paise, "currency": "INR"},
        )

    def verify_payment(self, provider_order_id: str, provider_payment_id: str, signature: str | None) -> PaymentVerification:
        if not signature:
            return PaymentVerification(verified=False, reason="Missing signature.")
        expected = hmac.new(
            self._key_secret.encode(), f"{provider_order_id}|{provider_payment_id}".encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return PaymentVerification(verified=False, reason="Signature mismatch.")
        return PaymentVerification(verified=True, providerPaymentId=provider_payment_id)

    def verify_webhook(self, raw_body: bytes, signature: str | None) -> tuple[PaymentVerification, str | None]:
        if not signature or not self._webhook_secret:
            return PaymentVerification(verified=False, reason="Missing signature or webhook secret."), None
        expected = hmac.new(self._webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return PaymentVerification(verified=False, reason="Webhook signature mismatch."), None
        try:
            payload = json.loads(raw_body)
            event = payload.get("event", "")
            if event in _IGNORED_BUT_LOGGED:
                ent = payload.get("payload", {}).get("payment", {}).get("entity", {})
                logger.warning("Razorpay %s for order %s: %s", event, ent.get("order_id"), ent.get("error_description"))
            if event not in _SUPPORTED_EVENTS:
                # Signature is valid but event type is not one we handle.
                # Return a distinct reason so the route can ACK with 200 (silence Razorpay retries).
                return PaymentVerification(verified=False, reason="unrecognised_event"), None
            entity = payload["payload"]["payment"]["entity"]
            order_id, payment_id = entity["order_id"], entity["id"]
            amount = entity["amount"] / 100 if isinstance(entity.get("amount"), (int, float)) else None
        except (KeyError, json.JSONDecodeError):
            return PaymentVerification(verified=False, reason="Malformed webhook payload."), None
        return PaymentVerification(verified=True, providerPaymentId=payment_id, amount=amount), order_id

    def fetch_captured_payment(self, provider_order_id: str) -> CapturedPayment | None:
        try:
            data = self._request("GET", f"/orders/{provider_order_id}/payments")
        except RuntimeError:
            logger.exception("Razorpay reconciliation fetch failed for %s", provider_order_id)
            return None
        for p in data.get("items", []):
            if p.get("status") == "captured":
                return CapturedPayment(providerPaymentId=p["id"], amount=p["amount"] / 100)
        return None

    def refund(self, provider_payment_id: str, amount: float) -> bool:
        paise = int(round(amount * 100))
        try:
            self._request("POST", f"/payments/{provider_payment_id}/refund", {"amount": paise})
            return True
        except RuntimeError:
            return False
