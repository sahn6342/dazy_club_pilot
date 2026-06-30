import { useState } from "react";
import { api, Order, Payment, Invoice } from "../lib/api";

type PayMode = "cash" | "upi" | "card";

interface PaymentModalProps {
  order: Order;
  onClose: () => void;
  onComplete: () => void;
}

const REF_LABEL: Record<string, string> = {
  upi: "UPI ref / Transaction ID (optional)",
  card: "Card / Transaction ID (optional)",
};

export function PaymentModal({ order, onClose, onComplete }: PaymentModalProps) {
  const [mode, setMode] = useState<PayMode>("cash");
  const [amount, setAmount] = useState(order.total.toFixed(2));
  const [reference, setReference] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [invoiceId, setInvoiceId] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const roundOff = order.total - (order.subtotal + order.taxAmount);

  async function handleRecordPayment() {
    setLoading(true);
    setError("");
    try {
      const payBody: Record<string, unknown> = {
        mode,
        amount: parseFloat(amount),
      };
      if (reference.trim() && (mode === "upi" || mode === "card")) {
        payBody.reference = reference.trim();
      }
      await api.post<Payment>(`/cafe/orders/${order.id}/payments`, payBody);
      const inv = await api.post<Invoice>(`/cafe/orders/${order.id}/invoice`, {});
      setInvoiceId(inv.id);
      setDone(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Payment failed.");
    } finally {
      setLoading(false);
    }
  }

  function handleOverlayClick(e: React.MouseEvent<HTMLDivElement>) {
    if (loading) return; // don't close during payment processing
    if (e.target === e.currentTarget) onClose();
  }

  function handlePrint() {
    window.open(`http://localhost:8000/api/v1/cafe/invoices/${invoiceId}/print`, "_blank");
  }

  function handleDone() {
    onComplete();
    onClose();
  }

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal-card">
        <div className="modal-title">Payment</div>

        <div>
          <div style={{ fontSize: "0.82rem", color: "var(--muted)", marginBottom: "0.25rem" }}>
            Order #{order.orderNo} · {order.items.length} item{order.items.length !== 1 ? "s" : ""}
          </div>
          <div className="modal-total">₹{order.total.toFixed(2)}</div>
          <div style={{ fontSize: "0.8rem", color: "var(--muted)", marginTop: "0.2rem" }}>
            Subtotal ₹{order.subtotal.toFixed(2)} + Tax ₹{order.taxAmount.toFixed(2)}
            {Math.abs(roundOff) >= 0.005 && (
              <> + Round off ₹{roundOff.toFixed(2)}</>
            )}
          </div>
        </div>

        {!done ? (
          <>
            <div>
              <div style={{ fontSize: "0.82rem", color: "var(--muted)", marginBottom: "0.4rem" }}>Payment Mode</div>
              <div className="pay-mode-row">
                {(["cash", "upi", "card"] as PayMode[]).map((m) => (
                  <button
                    key={m}
                    className={`pay-mode-btn${mode === m ? " active" : ""}`}
                    onClick={() => setMode(m)}
                  >
                    {m === "cash" ? "Cash" : m === "upi" ? "UPI" : "Card"}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div style={{ fontSize: "0.82rem", color: "var(--muted)", marginBottom: "0.4rem" }}>Amount (₹)</div>
              <input
                className="modal-input"
                type="number"
                step="0.01"
                min="0"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </div>

            {(mode === "upi" || mode === "card") && (
              <div>
                <div style={{ fontSize: "0.82rem", color: "var(--muted)", marginBottom: "0.4rem" }}>
                  {REF_LABEL[mode]}
                </div>
                <input
                  className="modal-input"
                  type="text"
                  placeholder="Enter reference"
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                />
              </div>
            )}

            {error && <div className="modal-error">{error}</div>}

            <div className="modal-actions">
              <button className="modal-btn secondary" onClick={onClose} disabled={loading}>
                Cancel
              </button>
              <button
                className="modal-btn primary"
                onClick={handleRecordPayment}
                disabled={loading || !amount || parseFloat(amount) <= 0}
              >
                {loading ? "Processing…" : "Record Payment"}
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="modal-success">Payment recorded successfully!</div>
            <div className="modal-actions">
              <button className="modal-btn secondary" onClick={handlePrint}>
                Print Receipt
              </button>
              <button className="modal-btn primary" onClick={handleDone}>
                Done
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
