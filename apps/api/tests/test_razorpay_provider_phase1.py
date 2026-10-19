"""Razorpay adapter additions: captured amount in webhooks, reconciliation fetch."""
import hashlib
import hmac
import json

import pytest

from integrations.payments.razorpay import RazorpayPaymentProvider


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_key")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "test_secret")
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "webhook_secret")
    return RazorpayPaymentProvider()


def test_verify_webhook_extracts_captured_amount_in_rupees(provider):
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {
        "order_id": "order_1", "id": "pay_1", "amount": 120050}}}}).encode()
    signature = hmac.new(b"webhook_secret", body, hashlib.sha256).hexdigest()
    result, _ = provider.verify_webhook(body, signature)
    assert result.verified is True and result.amount == 1200.50


def test_payment_failed_event_is_acknowledged_not_confirmed(provider):
    body = json.dumps({"event": "payment.failed", "payload": {"payment": {"entity": {
        "order_id": "order_1", "id": "pay_1", "error_description": "card declined"}}}}).encode()
    signature = hmac.new(b"webhook_secret", body, hashlib.sha256).hexdigest()
    result, order_id = provider.verify_webhook(body, signature)
    assert result.verified is False and result.reason == "unrecognised_event" and order_id is None


def test_fetch_captured_payment_returns_first_captured(provider, monkeypatch):
    monkeypatch.setattr(provider, "_request", lambda m, p, b=None: {"items": [
        {"id": "pay_fail", "status": "failed", "amount": 100},
        {"id": "pay_ok", "status": "captured", "amount": 120000}]})
    got = provider.fetch_captured_payment("order_1")
    assert got.providerPaymentId == "pay_ok" and got.amount == 1200.0


def test_fetch_captured_payment_none_when_unpaid_or_api_error(provider, monkeypatch):
    monkeypatch.setattr(provider, "_request", lambda m, p, b=None: {"items": [{"id": "p", "status": "failed", "amount": 1}]})
    assert provider.fetch_captured_payment("order_1") is None

    def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(provider, "_request", boom)
    assert provider.fetch_captured_payment("order_1") is None
