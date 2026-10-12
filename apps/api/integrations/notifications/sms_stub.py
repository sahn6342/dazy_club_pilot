"""SMS stub — prints to stdout. Swap for a real provider (e.g. Twilio, MSG91)
by setting DAZY_NOTIFY_SMS_PROVIDER and adding a real class."""
import uuid
from .base import NotificationProvider, NotificationResult


class SmsStubProvider(NotificationProvider):
    name = "sms_stub"

    def send(self, to: str, subject: str, body: str) -> NotificationResult:
        msg_id = f"sms-stub-{uuid.uuid4().hex[:8]}"
        print(f"[notify:sms] to={to} id={msg_id}\n{body}")
        return NotificationResult(status="sent", detail=msg_id)
