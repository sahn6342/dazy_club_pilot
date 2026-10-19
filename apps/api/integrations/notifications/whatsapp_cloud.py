"""WhatsApp via Meta's WhatsApp Business Cloud API (no BSP needed). Selected with
DAZY_NOTIFY_WHATSAPP_PROVIDER=whatsapp_cloud.

Env:
  WHATSAPP_CLOUD_TOKEN       permanent system-user access token
  WHATSAPP_CLOUD_PHONE_ID    phone-number id of the sending WhatsApp Business number
  WHATSAPP_OTP_TEMPLATE      name of an approved *authentication* template (one {{1}} code param)
  WHATSAPP_TEMPLATE_LANG     template language code (default "en")
  WHATSAPP_DEFAULT_COUNTRY_CODE  prepended to 10-digit numbers (default "91")

Business-initiated messages outside a 24 h customer window MUST use an approved template, so
OTPs go out as template messages. Booking notifications use plain text, which WhatsApp only
delivers inside that window; give them their own templates before relying on them.
NOTE: written against Meta's documented request shape and unit-tested with a mocked
transport; it has not been exercised against the live API."""
import json
import logging
import os
import urllib.error
import urllib.request

from .base import NotificationProvider, NotificationResult

logger = logging.getLogger(__name__)

_GRAPH = "https://graph.facebook.com/v20.0"


class WhatsAppCloudProvider(NotificationProvider):
    name = "whatsapp_cloud"

    def __init__(self):
        self._token = os.environ.get("WHATSAPP_CLOUD_TOKEN", "")
        self._phone_id = os.environ.get("WHATSAPP_CLOUD_PHONE_ID", "")
        self._otp_template = os.environ.get("WHATSAPP_OTP_TEMPLATE", "")
        self._lang = os.environ.get("WHATSAPP_TEMPLATE_LANG", "en")
        self._cc = os.environ.get("WHATSAPP_DEFAULT_COUNTRY_CODE", "91")

    def _to(self, number: str) -> str:
        digits = "".join(ch for ch in number if ch.isdigit())
        return f"{self._cc}{digits}" if len(digits) == 10 else digits

    def _post(self, payload: dict) -> NotificationResult:
        if not self._token or not self._phone_id:
            return NotificationResult(status="failed", detail="WHATSAPP_CLOUD_TOKEN/WHATSAPP_CLOUD_PHONE_ID not configured.")
        req = urllib.request.Request(
            f"{_GRAPH}/{self._phone_id}/messages", data=json.dumps(payload).encode(), method="POST",
            headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            return NotificationResult(status="sent", detail=(data.get("messages") or [{}])[0].get("id"))
        except urllib.error.HTTPError as e:
            return NotificationResult(status="failed", detail=f"WhatsApp API {e.code}: {e.read().decode()[:300]}")
        except Exception as exc:
            return NotificationResult(status="failed", detail=str(exc))

    def send(self, to: str, subject: str, body: str) -> NotificationResult:
        if "@" in to:
            return NotificationResult(status="skipped", detail="Recipient is not a phone number.")
        return self._post({"messaging_product": "whatsapp", "to": self._to(to), "type": "text",
                           "text": {"body": body}})

    def send_otp(self, to: str, code: str) -> NotificationResult:
        if not self._otp_template:
            return NotificationResult(status="failed", detail="WHATSAPP_OTP_TEMPLATE not configured.")
        return self._post({
            "messaging_product": "whatsapp", "to": self._to(to), "type": "template",
            "template": {
                "name": self._otp_template, "language": {"code": self._lang},
                "components": [
                    {"type": "body", "parameters": [{"type": "text", "text": code}]},
                    # Authentication templates carry a copy-code button that repeats the code.
                    {"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": code}]},
                ],
            },
        })
