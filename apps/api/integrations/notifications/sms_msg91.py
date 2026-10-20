"""SMS through MSG91's Flow API. Selected with DAZY_NOTIFY_SMS_PROVIDER=msg91.

India requires every transactional SMS to match a DLT-registered template, so MSG91 sends *templates*, never
free text: each event below needs a template created in MSG91 (and registered on DLT) whose variables are named
var1, var2, ... in the order documented in docs/App-Overview.md. An event without a configured template id is
skipped (and shown as skipped in the admin notification log) instead of failing noisily.

Env:
  MSG91_AUTH_KEY                 account auth key
  MSG91_TEMPLATE_BOOKING_CONFIRMED / _CANCELLED / _REFUNDED / _PENDING
                                 flow template ids for those events
  MSG91_TEMPLATE_OTP             flow template id for the login/search OTP (variable var1 = the code)
  WHATSAPP_DEFAULT_COUNTRY_CODE  prepended to 10-digit numbers (default "91"; shared with the WhatsApp adapter)

NOTE: written against MSG91's documented Flow API request shape and unit-tested with a mocked transport; it has
not been exercised against the live service."""
import json
import logging
import os
import urllib.error
import urllib.request

from .base import NotificationProvider, NotificationResult

logger = logging.getLogger(__name__)

_FLOW_URL = "https://control.msg91.com/api/v5/flow"
_EVENT_ENV = {
    "booking_pending": "MSG91_TEMPLATE_BOOKING_PENDING",
    "booking_confirmed": "MSG91_TEMPLATE_BOOKING_CONFIRMED",
    "booking_cancelled": "MSG91_TEMPLATE_BOOKING_CANCELLED",
    "booking_refunded": "MSG91_TEMPLATE_BOOKING_REFUNDED",
}


class Msg91SmsProvider(NotificationProvider):
    name = "msg91"

    def __init__(self):
        self._key = os.environ.get("MSG91_AUTH_KEY", "")
        self._cc = os.environ.get("WHATSAPP_DEFAULT_COUNTRY_CODE", "91")

    def _to(self, number: str) -> str:
        digits = "".join(ch for ch in number if ch.isdigit())
        return f"{self._cc}{digits}" if len(digits) == 10 else digits

    def _flow(self, template_id: str, to: str, params: list[str]) -> NotificationResult:
        if not self._key:
            return NotificationResult(status="failed", detail="MSG91_AUTH_KEY not configured.", retryable=False)
        recipient = {"mobiles": self._to(to)}
        recipient.update({f"var{i}": str(v) for i, v in enumerate(params, start=1)})
        req = urllib.request.Request(
            _FLOW_URL, method="POST",
            data=json.dumps({"template_id": template_id, "short_url": "0", "recipients": [recipient]}).encode(),
            headers={"authkey": self._key, "Content-Type": "application/json", "accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            transient = e.code >= 500 or e.code == 429
            return NotificationResult(status="failed", detail=f"MSG91 {e.code}: {e.read().decode(errors='replace')[:300]}", retryable=transient)
        except Exception as exc:  # timeouts, DNS, resets
            return NotificationResult(status="failed", detail=str(exc), retryable=True)
        # MSG91 answers 200 with {"type": "error", "message": ...} for rejected requests (bad template, no balance...).
        if str(data.get("type", "")).lower() == "error":
            return NotificationResult(status="failed", detail=f"MSG91: {data.get('message', 'rejected')}", retryable=False)
        return NotificationResult(status="sent", detail=data.get("message") or data.get("request_id"))

    def send(self, to: str, subject: str, body: str) -> NotificationResult:
        if "@" in to:
            return NotificationResult(status="skipped", detail="Recipient is not a phone number.")
        return NotificationResult(status="skipped", detail="MSG91 sends DLT templates only; free-text SMS is not possible.")

    def send_template(self, to: str, event: str, params: list[str], fallback_subject: str, fallback_body: str) -> NotificationResult:
        if "@" in to:
            return NotificationResult(status="skipped", detail="Recipient is not a phone number.")
        env = _EVENT_ENV.get(event)
        template_id = os.environ.get(env, "") if env else ""
        if not template_id:
            return NotificationResult(status="skipped", detail=f"No MSG91 template configured for {event} ({env or 'unknown event'}).")
        return self._flow(template_id, to, params)

    def send_otp(self, to: str, code: str) -> NotificationResult:
        template_id = os.environ.get("MSG91_TEMPLATE_OTP", "")
        if not template_id:
            return NotificationResult(status="failed", detail="MSG91_TEMPLATE_OTP not configured.", retryable=False)
        return self._flow(template_id, to, [code])
