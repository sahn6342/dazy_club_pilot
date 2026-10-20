"""WhatsApp stub: logs instead of sending. Swap for a real provider (e.g. Twilio,
WATI) by setting DAZY_NOTIFY_WHATSAPP_PROVIDER and adding a real class.
In production the body (it can carry an OTP code) and the full recipient are not logged."""
import logging
import uuid

from logging_config import _is_production, mask_contact
from .base import NotificationProvider, NotificationResult

logger = logging.getLogger("notify.whatsapp")


class WhatsAppStubProvider(NotificationProvider):
    name = "whatsapp_stub"

    def send(self, to: str, subject: str, body: str) -> NotificationResult:
        msg_id = f"whatsapp-stub-{uuid.uuid4().hex[:8]}"
        if _is_production():
            logger.warning("whatsapp stub active in production: NOT delivered to %s (id=%s)", mask_contact(to), msg_id)
        else:
            logger.info("notify.whatsapp to=%s id=%s\n%s", to, msg_id, body)
        return NotificationResult(status="sent", detail=msg_id)
