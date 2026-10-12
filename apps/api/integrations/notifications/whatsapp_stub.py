"""WhatsApp stub — prints to stdout. Swap for a real provider (e.g. Twilio,
WATI) by setting DAZY_NOTIFY_WHATSAPP_PROVIDER and adding a real class."""
import uuid
from .base import NotificationProvider, NotificationResult


class WhatsAppStubProvider(NotificationProvider):
    name = "whatsapp_stub"

    def send(self, to: str, subject: str, body: str) -> NotificationResult:
        msg_id = f"whatsapp-stub-{uuid.uuid4().hex[:8]}"
        print(f"[notify:whatsapp] to={to} id={msg_id}\n{body}")
        return NotificationResult(status="sent", detail=msg_id)
