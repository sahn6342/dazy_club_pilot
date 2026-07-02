import { useState } from "react";
import type { CheckoutConfig } from "../lib/api";
import { verifyBookingPayment } from "../lib/api";

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
  }
}

let razorpayScriptPromise: Promise<void> | null = null;

function loadRazorpayScript(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  if (!razorpayScriptPromise) {
    razorpayScriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://checkout.razorpay.com/v1/checkout.js";
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Could not load the payment gateway. Check your connection and try again."));
      document.body.appendChild(script);
    });
  }
  return razorpayScriptPromise;
}

interface PaymentPanelProps {
  bookingRef: string;
  checkout: CheckoutConfig;
  amount: number;
  customerName: string;
  customerContact: string;
  onSuccess: () => void;
}

export function PaymentPanel({ bookingRef, checkout, amount, customerName, customerContact, onSuccess }: PaymentPanelProps) {
  const [status, setStatus] = useState<"idle" | "processing" | "dismissed" | "error">("idle");
  const [error, setError] = useState("");

  async function completeVerification(providerPaymentId: string, signature?: string) {
    setStatus("processing");
    setError("");
    try {
      await verifyBookingPayment(bookingRef, { providerOrderId: checkout.providerOrderId, providerPaymentId, signature });
      onSuccess();
    } catch (err: any) {
      setStatus("error");
      setError(err?.message ?? "We couldn't confirm your payment. Please try again or contact us with your booking ref.");
    }
  }

  async function openRazorpay() {
    setStatus("processing");
    setError("");
    try {
      await loadRazorpayScript();
      const rzp = new window.Razorpay!({
        key: checkout.key,
        order_id: checkout.order_id,
        amount: checkout.amount,
        currency: checkout.currency,
        name: "Dazy.club",
        description: `Booking ${bookingRef}`,
        prefill: { name: customerName, contact: customerContact },
        theme: { color: "#d8b456" },
        handler: (response: { razorpay_payment_id: string; razorpay_order_id: string; razorpay_signature: string }) => {
          completeVerification(response.razorpay_payment_id, response.razorpay_signature);
        },
        modal: {
          ondismiss: () => setStatus("dismissed"),
        },
      });
      rzp.open();
    } catch (err: any) {
      setStatus("error");
      setError(err?.message ?? "Could not start the payment gateway.");
    }
  }

  const isDev = checkout.provider === "noop";

  return (
    <div className="payment-panel">
      <p className="eyebrow">Payment required</p>
      <h3>Complete payment to confirm your booking</h3>
      <p className="summary-total" data-testid="payment-amount">Amount due: ₹{amount.toFixed(2)}</p>
      <p className="muted">Ref: {bookingRef} — your slot is held for 15 minutes while you pay.</p>

      {error && <p className="form-message error" data-testid="payment-error">{error}</p>}

      {isDev ? (
        <div className="payment-dev-panel" data-testid="payment-dev-panel">
          <p className="muted">Dev mode — no real payment gateway is configured.</p>
          <div className="payment-dev-actions">
            <button
              type="button"
              className="button primary"
              disabled={status === "processing"}
              data-testid="simulate-payment-success"
              onClick={() => completeVerification(`noop_pay_${Date.now()}`)}
            >
              {status === "processing" ? "Confirming…" : "Simulate successful payment"}
            </button>
            <button
              type="button"
              className="button secondary"
              disabled={status === "processing"}
              data-testid="simulate-payment-failure"
              onClick={() => { setStatus("dismissed"); setError(""); }}
            >
              Simulate failed / cancelled payment
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          className="button primary"
          disabled={status === "processing"}
          onClick={openRazorpay}
        >
          {status === "processing" ? "Opening payment…" : status === "dismissed" ? "Try payment again" : "Pay now"}
        </button>
      )}

      {status === "dismissed" && !isDev && (
        <p className="form-message" data-testid="payment-dismissed">
          Payment was cancelled. Your slot is still held for a few minutes — try again when ready.
        </p>
      )}
    </div>
  );
}
