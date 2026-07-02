import os

from .base import NotificationProvider


def get_notification_provider() -> NotificationProvider:
    provider = os.environ.get("DAZY_NOTIFY_PROVIDER", "console")
    if provider == "email":
        from .email_smtp import SmtpEmailNotificationProvider
        return SmtpEmailNotificationProvider()
    from .console import ConsoleNotificationProvider
    return ConsoleNotificationProvider()
