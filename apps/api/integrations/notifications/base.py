"""Notification provider adapter — pluggable via DAZY_NOTIFY_PROVIDER (default:
console, see factory.py). A real provider drops in with zero call-site
changes, matching the deferred-notification-provider decision (DEC-008,
extended by DEC-026)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class NotificationResult:
    status: str  # sent | skipped | failed
    detail: str | None = None


class NotificationProvider(ABC):
    name: str

    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> NotificationResult: ...
