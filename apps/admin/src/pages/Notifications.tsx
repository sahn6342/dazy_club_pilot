import { useCallback, useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";

type Notification = {
  id: string; refType: string; refId: string; channel: string; recipient: string; status: string;
  errorMessage: string | null; createdAt: string; event: string | null; provider: string | null;
  attempts: number; lastAttemptAt: string | null; nextAttemptAt: string | null; resendable: boolean;
};

const PAGE_SIZE = 50;
const TABS = [
  { label: "All", value: "" },
  { label: "Failed", value: "failed" },
  { label: "Retrying", value: "retrying" },
  { label: "Skipped", value: "skipped" },
  { label: "Sent", value: "sent" },
];
const STATUS_STYLE: Record<string, string> = { sent: "green", failed: "red", retrying: "gold", skipped: "grey", sending: "gold" };
const EVENT_LABEL: Record<string, string> = {
  booking_pending: "Payment reminder", booking_confirmed: "Confirmation", booking_cancelled: "Cancellation", booking_refunded: "Refund",
};

export function Notifications() {
  const toast = useToast();
  const [items, setItems] = useState<Notification[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [channel, setChannel] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  const load = useCallback(() => {
    const p = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
    if (status) p.set("status", status);
    if (channel) p.set("channel", channel);
    api.list<Notification>(`/admin/notifications?${p}`)
      .then((r) => { setItems(r.items); setTotal(r.total); setError(""); })
      .catch((e) => setError(e?.message ?? "Could not load notifications"));
  }, [status, channel, offset]);

  useEffect(() => { load(); }, [load, reload]);

  async function resend(n: Notification) {
    setBusy(n.id);
    try {
      const r = await api.post<Notification>(`/admin/notifications/${n.id}/resend`, {});
      if (r.status === "sent") toast.success("Message sent");
      else toast.error(`Not sent: ${r.errorMessage ?? r.status}`);
      setReload((k) => k + 1);
    } catch (e: any) {
      toast.error(e?.message ?? "Could not resend");
    } finally {
      setBusy(null);
    }
  }

  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Notifications" />
        <div className="page-body">
          <p className="muted" style={{ marginTop: 0, fontSize: "0.85rem" }}>
            Every email, SMS and WhatsApp the system sent or tried to send. Temporary failures are retried automatically
            (after 2 and 10 minutes); anything still failed can be resent by hand.
          </p>
          <div className="tab-bar">
            {TABS.map((t) => (
              <button key={t.label} data-testid={`tab-${t.value || "all"}`} className={`tab-btn${status === t.value ? " active" : ""}`}
                onClick={() => { setStatus(t.value); setOffset(0); }}>
                {t.label}
              </button>
            ))}
          </div>
          <div className="filter-bar">
            <select data-testid="channel-filter" value={channel} onChange={(e) => { setChannel(e.target.value); setOffset(0); }}>
              <option value="">All channels</option>
              <option value="email">Email</option>
              <option value="sms">SMS</option>
              <option value="whatsapp">WhatsApp</option>
            </select>
          </div>

          {error ? (
            <p className="error-msg">{error}</p>
          ) : items.length === 0 ? (
            <p className="empty-msg">No notifications match.</p>
          ) : (
            <div className="table-wrap">
              <table data-testid="notifications-table">
                <thead>
                  <tr><th>When</th><th>Message</th><th>Channel</th><th>To</th><th>Status</th><th>Details</th><th /></tr>
                </thead>
                <tbody>
                  {items.map((n) => (
                    <tr key={n.id} data-testid={`notification-${n.id}`}>
                      <td style={{ whiteSpace: "nowrap" }}>{new Date(n.createdAt).toLocaleString()}</td>
                      <td>{n.event ? (EVENT_LABEL[n.event] ?? n.event) : n.refType}</td>
                      <td style={{ textTransform: "capitalize" }}>{n.channel}</td>
                      <td>{n.recipient}</td>
                      <td>
                        <span className={`status-badge ${STATUS_STYLE[n.status] ?? "grey"}`} data-testid="notification-status">{n.status}</span>
                        {n.attempts > 1 && <small className="muted" style={{ display: "block" }}>attempt {n.attempts}</small>}
                      </td>
                      <td style={{ maxWidth: 360, wordBreak: "break-word" }} className="muted">
                        {n.errorMessage}
                        {n.status === "retrying" && n.nextAttemptAt && <> · next try {new Date(n.nextAttemptAt).toLocaleTimeString()}</>}
                      </td>
                      <td>
                        {n.resendable && (
                          <button className="btn-action confirm" data-testid={`resend-${n.id}`} disabled={busy === n.id} onClick={() => resend(n)}>
                            {busy === n.id ? "Sending…" : "Resend"}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {!error && (
            <div className="pagination-bar">
              <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>← Newer</button>
              <span data-testid="notifications-range">{from}–{to} of {total}</span>
              <button disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>Older →</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
