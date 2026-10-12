import os

from .base import NotificationProvider


def get_notification_provider() -> NotificationProvider:
    provider = os.environ.get("DAZY_NOTIFY_PROVIDER", "console")
    if provider == "email":
        from .email_smtp import SmtpEmailNotificationProvider
        return SmtpEmailNotificationProvider()
    from .console import ConsoleNotificationProvider
    return ConsoleNotificationProvider()


def get_whatsapp_provider() -> NotificationProvider:
    provider = os.environ.get("DAZY_NOTIFY_WHATSAPP_PROVIDER", "whatsapp_stub")
    from .whatsapp_stub import WhatsAppStubProvider
    return WhatsAppStubProvider()


def get_sms_provider() -> NotificationProvider:
    provider = os.environ.get("DAZY_NOTIFY_SMS_PROVIDER", "sms_stub")
    from .sms_stub import SmsStubProvider
    return SmsStubProvider()
