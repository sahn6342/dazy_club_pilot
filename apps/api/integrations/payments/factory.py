import os

from .base import PaymentProvider


def get_payment_provider() -> PaymentProvider:
    provider = os.environ.get("DAZY_PAYMENT_PROVIDER", "noop")
    if provider == "razorpay":
        from .razorpay import RazorpayPaymentProvider
        return RazorpayPaymentProvider()
    from .noop import NoopPaymentProvider
    return NoopPaymentProvider()
