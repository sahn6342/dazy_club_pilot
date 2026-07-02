"""SMTP email notification provider (stdlib smtplib — zero new deps, same
approach as the Razorpay payment adapter's stdlib urllib). Requires
SMTP_HOST/SMTP_USER/SMTP_PASSWORD (+ optional SMTP_PORT/SMTP_FROM) env vars.
Only sends when `to` looks like an email address — a phone-number contact is
skipped, not failed, since SMS is a documented-not-built alternative channel
(Detailed-Roadmap Phase 5)."""
import os
import smtplib
from email.mime.text import MIMEText

from .base import NotificationProvider, NotificationResult


class SmtpEmailNotificationProvider(NotificationProvider):
    name = "email"

    def send(self, to: str, subject: str, body: str) -> NotificationResult:
        if "@" not in to:
            return NotificationResult(status="skipped", detail="Recipient is not an email address; SMS is not configured.")

        host = os.environ.get("SMTP_HOST")
        user = os.environ.get("SMTP_USER")
        password = os.environ.get("SMTP_PASSWORD")
        if not host or not user or not password:
            return NotificationResult(status="failed", detail="SMTP_HOST/SMTP_USER/SMTP_PASSWORD not configured.")

        port = int(os.environ.get("SMTP_PORT", "587"))
        sender = os.environ.get("SMTP_FROM", user)

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to
        try:
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.starttls()
                server.login(user, password)
                server.sendmail(sender, [to], msg.as_string())
            return NotificationResult(status="sent")
        except Exception as exc:
            return NotificationResult(status="failed", detail=str(exc))
