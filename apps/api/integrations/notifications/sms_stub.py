"""SMS stub: logs instead of sending. Swap for a real provider (e.g. Twilio, MSG91)
by setting DAZY_NOTIFY_SMS_PROVIDER and adding a real class.
In production the body (it can carry an OTP code) and the full recipient are not logged."""
import logging
import uuid

from logging_config import _is_production, mask_contact
from .base import NotificationProvider, NotificationResult

logger = logging.getLogger("notify.sms")


class SmsStubProvider(NotificationProvider):
    name = "sms_stub"

    def send(self, to: str, subject: str, body: str) -> NotificationResult:
        msg_id = f"sms-stub-{uuid.uuid4().hex[:8]}"
        if _is_production():
            logger.warning("sms stub active in production: NOT delivered to %s (id=%s)", mask_contact(to), msg_id)
        else:
            logger.info("notify.sms to=%s id=%s\n%s", to, msg_id, body)
        return NotificationResult(status="sent", detail=msg_id)
