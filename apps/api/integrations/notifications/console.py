"""Dev/test notification provider: logs the message instead of sending it, so booking confirmations
and OTP codes can be exercised end to end without an email/SMS provider.

In production the body (which can hold an OTP code) and the full recipient are NOT logged: using this
provider there means nothing is delivered, and the log must not become a place to read customers'
codes. Configure DAZY_NOTIFY_PROVIDER=email for real delivery."""
import logging

from logging_config import _is_production, mask_contact
from .base import NotificationProvider, NotificationResult

logger = logging.getLogger("notify.console")


class ConsoleNotificationProvider(NotificationProvider):
    name = "console"

    def send(self, to: str, subject: str, body: str) -> NotificationResult:
        if _is_production():
            logger.warning("Console notify provider active in production: NOT delivered to %s (%r)", mask_contact(to), subject)
        else:
            logger.info("notify.console to=%s subject=%r\n%s", to, subject, body)
        return NotificationResult(status="sent", detail="console")
