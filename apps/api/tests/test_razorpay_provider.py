"""
Razorpay signature verification — pure crypto logic, no network calls needed
for these two methods (create_order/refund do hit the Razorpay REST API and
are intentionally not exercised here without real credentials).
"""
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


def test_verify_payment_correct_signature_accepted(provider):
    order_id, payment_id = "order_ABC123", "pay_XYZ789"
    signature = hmac.new(b"test_secret", f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    result = provider.verify_payment(order_id, payment_id, signature)
    assert result.verified is True
    assert result.providerPaymentId == payment_id


def test_verify_payment_wrong_signature_rejected(provider):
    result = provider.verify_payment("order_ABC123", "pay_XYZ789", "0" * 64)
    assert result.verified is False
    assert "mismatch" in result.reason.lower()


def test_verify_payment_missing_signature_rejected(provider):
    result = provider.verify_payment("order_ABC123", "pay_XYZ789", None)
    assert result.verified is False


def test_verify_webhook_correct_signature_extracts_order_id(provider):
    body = json.dumps({"payload": {"payment": {"entity": {"order_id": "order_1", "id": "pay_1"}}}}).encode()
    signature = hmac.new(b"webhook_secret", body, hashlib.sha256).hexdigest()
    result, order_id = provider.verify_webhook(body, signature)
    assert result.verified is True
    assert result.providerPaymentId == "pay_1"
    assert order_id == "order_1"


def test_verify_webhook_wrong_signature_rejected(provider):
    body = json.dumps({"payload": {"payment": {"entity": {"order_id": "order_1", "id": "pay_1"}}}}).encode()
    result, order_id = provider.verify_webhook(body, "deadbeef" * 8)
    assert result.verified is False
    assert order_id is None


def test_verify_webhook_malformed_payload_rejected(provider):
    body = json.dumps({"unexpected": "shape"}).encode()
    signature = hmac.new(b"webhook_secret", body, hashlib.sha256).hexdigest()
    result, order_id = provider.verify_webhook(body, signature)
    assert result.verified is False
    assert order_id is None


def test_verify_webhook_missing_webhook_secret_rejected(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_key")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "test_secret")
    monkeypatch.delenv("RAZORPAY_WEBHOOK_SECRET", raising=False)
    p = RazorpayPaymentProvider()
    result, order_id = p.verify_webhook(b"{}", "somesig")
    assert result.verified is False
