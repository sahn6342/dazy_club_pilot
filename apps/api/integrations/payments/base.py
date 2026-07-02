"""Payment provider adapter — pluggable via DAZY_PAYMENT_PROVIDER (default: noop,
see factory.py). Real gateway integration (Razorpay) drops in with zero
call-site changes, matching the deferred-payment-provider decision (DEC-007,
extended by DEC-026)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PaymentOrder:
    provider: str
    providerOrderId: str
    amount: float
    currency: str
    checkout: dict  # opaque, frontend-consumed config (Razorpay: key/order_id/amount; noop: enough to fake a UI)


@dataclass
class PaymentVerification:
    verified: bool
    providerPaymentId: str | None = None
    reason: str | None = None


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    def create_order(self, amount: float, ref: str) -> PaymentOrder: ...

    @abstractmethod
    def verify_payment(
        self, provider_order_id: str, provider_payment_id: str, signature: str | None
    ) -> PaymentVerification: ...

    @abstractmethod
    def verify_webhook(
        self, raw_body: bytes, signature: str | None
    ) -> tuple[PaymentVerification, str | None]:
        """Returns (verification, provider_order_id). The order id is pulled
        from the now-trusted payload so the caller can look up the booking —
        never trust an order id passed outside the signed payload/body."""
        ...

    @abstractmethod
    def refund(self, provider_payment_id: str, amount: float) -> bool: ...
