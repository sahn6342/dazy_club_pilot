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
    if provider == "whatsapp_cloud":
        from .whatsapp_cloud import WhatsAppCloudProvider
        return WhatsAppCloudProvider()
    from .whatsapp_stub import WhatsAppStubProvider
    return WhatsAppStubProvider()


def get_sms_provider() -> NotificationProvider:
    provider = os.environ.get("DAZY_NOTIFY_SMS_PROVIDER", "sms_stub")
    if provider == "msg91":
        from .sms_msg91 import Msg91SmsProvider
        return Msg91SmsProvider()
    from .sms_stub import SmsStubProvider
    return SmsStubProvider()
