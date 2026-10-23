import { useEffect, useState } from "react";
import { api } from "../lib/api";

type Quote = {
  paid: number; refunded: number; remaining: number; hoursBefore: number;
  percent: number; policyAmount: number; suggestedAmount: number;
  nonRefundable?: number; // part of `paid` that is never refunded (the advance)
};
type QuoteResponse = { bookingRef: string; refundable: boolean; cancellable: boolean; quote: Quote | null };

export type RefundTarget = { id: string; bookingRef: string; name: string; date: string; startTime: string };

const inr = (n: number) => `₹${n.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

function startsIn(hours: number): string {
  if (hours < 0) return `started ${Math.abs(hours).toFixed(1)} h ago`;
  if (hours < 48) return `starts in ${hours.toFixed(1)} h`;
  return `starts in ${(hours / 24).toFixed(1)} days`;
}

/**
 * "cancel": cancel the booking and refund per the notice policy (amount editable, 0 = no refund).
 * "refund": refund part or all of what was paid without touching the booking unless the balance hits zero.
 */
export function RefundDialog({
  booking, mode, onClose, onDone,
}: {
  booking: RefundTarget; mode: "cancel" | "refund"; onClose: () => void; onDone: (message: string) => void;
}) {
  const [data, setData] = useState<QuoteResponse | null>(null);
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<QuoteResponse>(`/admin/bookings/${booking.id}/refund-quote`)
      .then((d) => {
        setData(d);
        const q = d.quote;
        setAmount(q ? String(mode === "cancel" ? q.suggestedAmount : q.remaining) : "0");
      })
      .catch((e) => setLoadError(e?.message ?? "Could not load the refund details."));
  }, [booking.id, mode]);

  const q = data?.quote ?? null;
  const remaining = q?.remaining ?? 0;
  const value = Number(amount);
  const invalid =
    amount.trim() === "" || Number.isNaN(value) || value < 0 || value > remaining + 0.0001 ||
    (mode === "refund" && value <= 0);
  const label =
    mode === "refund"
      ? `Refund ${inr(value || 0)}`
      : value > 0 ? `Cancel booking & refund ${inr(value)}` : "Cancel booking, no refund";

  async function submit() {
    if (invalid || busy) return;
    setBusy(true);
    setError("");
    try {
      const body = { amount: value, reason: reason.trim() || undefined };
      const res = await api.post<{ refunded: number; paymentStatus: string }>(
        mode === "cancel" ? `/admin/bookings/${booking.id}/cancel-and-refund` : `/admin/bookings/${booking.id}/refund`,
        body,
      );
      onDone(
        mode === "cancel"
          ? (res.refunded > 0 ? `Booking cancelled, ${inr(res.refunded)} refunded` : "Booking cancelled, no refund")
          : `${inr(res.refunded)} refunded`,
      );
    } catch (e: any) {
      setError(e?.message ?? "The refund could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="confirm-overlay" role="dialog" aria-modal="true" data-testid="refund-dialog"
      onClick={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <div className="confirm-dialog" style={{ maxWidth: 440, textAlign: "left" }}>
        <h3 style={{ margin: "0 0 0.25rem" }}>{mode === "cancel" ? "Cancel booking" : "Refund payment"}</h3>
        <p className="muted" style={{ margin: "0 0 0.75rem", fontSize: "0.85rem" }}>
          {booking.bookingRef} · {booking.name} · {booking.date} {booking.startTime}
        </p>

        {loadError && <p className="field-error">{loadError}</p>}
        {!data && !loadError && <p className="muted">Loading…</p>}

        {data && !q && (
          <p className="muted" data-testid="refund-nothing">
            Nothing was paid online for this booking, so there is nothing to refund.
          </p>
        )}

        {q && (
          <>
            <p style={{ margin: "0 0 0.5rem", fontSize: "0.9rem" }} data-testid="refund-summary">
              Paid <strong>{inr(q.paid)}</strong>
              {q.refunded > 0 && <> · already refunded <strong>{inr(q.refunded)}</strong></>}
              {" "}· refundable <strong>{inr(q.remaining)}</strong>
            </p>
            {(q.nonRefundable ?? 0) > 0 && (
              <p className="muted" style={{ margin: "0 0 0.5rem", fontSize: "0.85rem" }} data-testid="refund-advance-note">
                The {inr(q.nonRefundable!)} advance is non-refundable.
                {q.remaining <= 0 && <> There is nothing to refund: cancelling only frees the slot.</>}
              </p>
            )}
            {mode === "cancel" && (
              <p style={{ margin: "0 0 0.75rem", fontSize: "0.9rem" }} data-testid="refund-policy-line">
                Booking {startsIn(q.hoursBefore)} → policy refunds <strong>{q.percent}%</strong> = <strong>{inr(q.policyAmount)}</strong>
                {q.suggestedAmount < q.policyAmount && <> (capped at the refundable balance)</>}
              </p>
            )}
            <label style={{ display: "block", fontSize: "0.85rem" }}>
              Refund amount (₹)
              <input data-testid="refund-amount" type="number" min={0} max={remaining} step="0.01"
                className="cms-textarea" style={{ display: "block", width: "100%", marginTop: "0.25rem", padding: "0.45rem 0.65rem" }}
                value={amount} onChange={(e) => setAmount(e.target.value)} />
            </label>
            <div style={{ display: "flex", gap: "0.4rem", margin: "0.5rem 0", flexWrap: "wrap" }}>
              {mode === "cancel" && (
                <button type="button" className="btn-action secondary" onClick={() => setAmount(String(q.suggestedAmount))}>Policy amount</button>
              )}
              <button type="button" className="btn-action secondary" onClick={() => setAmount(String(q.remaining))}>Full balance</button>
              {mode === "cancel" && (
                <button type="button" className="btn-action secondary" onClick={() => setAmount("0")}>No refund</button>
              )}
            </div>
            {amount !== "" && !Number.isNaN(value) && value > remaining + 0.0001 && (
              <p className="field-error">Cannot exceed the refundable balance ({inr(remaining)}).</p>
            )}
            {mode === "refund" && amount !== "" && value <= 0 && <p className="field-error">Enter an amount above zero.</p>}
          </>
        )}

        {data && (
          <label style={{ display: "block", fontSize: "0.85rem", marginTop: "0.5rem" }}>
            Reason (optional, kept in the audit log)
            <input data-testid="refund-reason" className="cms-textarea" maxLength={500}
              style={{ display: "block", width: "100%", marginTop: "0.25rem", padding: "0.45rem 0.65rem" }}
              value={reason} onChange={(e) => setReason(e.target.value)} />
          </label>
        )}

        {error && <p className="field-error" data-testid="refund-error">{error}</p>}

        <div className="confirm-actions" style={{ marginTop: "1rem" }}>
          <button className="btn-action cancel" onClick={onClose} disabled={busy}>Keep booking</button>
          {data && (mode === "cancel" || q) && (
            <button className="btn-action confirm" data-testid="refund-submit"
              disabled={busy || (!!q && invalid) || (!q && mode === "refund")} onClick={submit}>
              {busy ? "Working…" : q ? label : "Cancel booking"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
