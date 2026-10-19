import os

from .base import PaymentProvider


def get_payment_provider() -> PaymentProvider:
    from config_guard import forbid_noop_payments_in_production
    provider = os.environ.get("DAZY_PAYMENT_PROVIDER", "noop")
    forbid_noop_payments_in_production(provider)
    if provider == "razorpay":
        from .razorpay import RazorpayPaymentProvider
        return RazorpayPaymentProvider()
    from .noop import NoopPaymentProvider
    return NoopPaymentProvider()
