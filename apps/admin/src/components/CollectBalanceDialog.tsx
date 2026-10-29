import { useState } from "react";
import { api } from "../lib/api";

/** `thenComplete`: opened from the Complete button, so the booking is marked completed as well. */
export type CollectTarget = { id: string; bookingRef: string; name: string; balanceDue: number; thenComplete?: boolean };

const inr = (n: number) => `₹${n.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

/** Record the balance of an advance booking taken at the venue (cash, UPI or card). */
export function CollectBalanceDialog({
  booking, onClose, onDone, onSkip,
}: {
  booking: CollectTarget; onClose: () => void; onDone: (message: string) => void;
  /** Complete the booking without collecting (only with `thenComplete`); the balance stays due. */
  onSkip?: () => void;
}) {
  const [mode, setMode] = useState<"cash" | "upi" | "card">("cash");
  const [amount, setAmount] = useState(String(booking.balanceDue));
  const [reference, setReference] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const value = Number(amount);
  const invalid = amount.trim() === "" || Number.isNaN(value) || value <= 0 || value > booking.balanceDue + 0.0001;

  async function submit() {
    if (invalid || busy) return;
    setBusy(true);
    setError("");
    try {
      await api.post(`/admin/bookings/${booking.id}/collect-balance`, { mode, amount: value, reference: reference.trim() || undefined });
      if (booking.thenComplete) await api.patch(`/admin/bookings/${booking.id}`, { status: "completed" });
      onDone(`${inr(value)} collected (${mode.toUpperCase()}) for ${booking.bookingRef}${booking.thenComplete ? " and the booking is completed" : ""}`);
    } catch (e: any) {
      setError(e?.message ?? "The balance could not be recorded.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="confirm-overlay" role="dialog" aria-modal="true" data-testid="collect-dialog"
      onClick={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <div className="confirm-dialog" style={{ maxWidth: 420, textAlign: "left" }}>
        <h3 style={{ margin: "0 0 0.25rem" }}>{booking.thenComplete ? "Complete booking" : "Collect balance"}</h3>
        <p className="muted" style={{ margin: "0 0 0.75rem", fontSize: "0.85rem" }}>
          {booking.bookingRef} · {booking.name} · balance due <strong data-testid="collect-due">{inr(booking.balanceDue)}</strong>
        </p>

        <label style={{ display: "block", fontSize: "0.85rem" }}>
          Paid by
          <select data-testid="collect-mode" className="cms-textarea" value={mode}
            style={{ display: "block", width: "100%", marginTop: "0.25rem", padding: "0.45rem 0.65rem" }}
            onChange={(e) => setMode(e.target.value as "cash" | "upi" | "card")}>
            <option value="cash">Cash</option>
            <option value="upi">UPI</option>
            <option value="card">Card</option>
          </select>
        </label>

        <label style={{ display: "block", fontSize: "0.85rem", marginTop: "0.5rem" }}>
          Amount (₹)
          <input data-testid="collect-amount" type="number" min={0} max={booking.balanceDue} step="0.01" className="cms-textarea"
            style={{ display: "block", width: "100%", marginTop: "0.25rem", padding: "0.45rem 0.65rem" }}
            value={amount} onChange={(e) => setAmount(e.target.value)} />
        </label>
        {amount !== "" && !Number.isNaN(value) && value > booking.balanceDue + 0.0001 && (
          <p className="field-error">Cannot exceed the balance due ({inr(booking.balanceDue)}).</p>
        )}

        <label style={{ display: "block", fontSize: "0.85rem", marginTop: "0.5rem" }}>
          Reference (optional, kept in the audit log)
          <input data-testid="collect-reference" className="cms-textarea" maxLength={100}
            style={{ display: "block", width: "100%", marginTop: "0.25rem", padding: "0.45rem 0.65rem" }}
            value={reference} onChange={(e) => setReference(e.target.value)} />
        </label>

        {error && <p className="field-error" data-testid="collect-error">{error}</p>}

        <div className="confirm-actions" style={{ marginTop: "1rem" }}>
          <button className="btn-action cancel" onClick={onClose} disabled={busy}>Close</button>
          {booking.thenComplete && onSkip && (
            <button className="btn-action secondary" data-testid="collect-skip" disabled={busy} onClick={onSkip}>Complete without collecting</button>
          )}
          <button className="btn-action confirm" data-testid="collect-submit" disabled={busy || invalid} onClick={submit}>
            {busy ? "Saving…" : booking.thenComplete ? `Collect ${inr(value || 0)} & complete` : `Collect ${inr(value || 0)}`}
          </button>
        </div>
      </div>
    </div>
  );
}
