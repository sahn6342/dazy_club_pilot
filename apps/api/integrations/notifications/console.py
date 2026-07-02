"""Dev/test notification provider — prints to stdout instead of sending a
real message. Lets booking-confirmation delivery be exercised end-to-end
without an SMS/email provider configured."""
from .base import NotificationProvider, NotificationResult


class ConsoleNotificationProvider(NotificationProvider):
    name = "console"

    def send(self, to: str, subject: str, body: str) -> NotificationResult:
        print(f"[notify:console] to={to} subject={subject!r}\n{body}")
        return NotificationResult(status="sent", detail="console")
