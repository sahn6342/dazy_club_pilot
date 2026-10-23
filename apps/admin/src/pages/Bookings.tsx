import { useEffect, useState } from "react";
import { useConfirm } from "../components/ConfirmDialog";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import { RefundDialog, type RefundTarget } from "../components/RefundDialog";
import { CollectBalanceDialog, type CollectTarget } from "../components/CollectBalanceDialog";

type Booking = {
  id: string; bookingRef: string; name: string; contact: string;
  sportSlug: string; date: string; startTime: string; endTime: string;
  party_size: number; price: number | null; promo_code: string | null;
  gst_rate_percent: number | null; status: string; paymentStatus: string; createdAt: string;
  deleted_at?: string | null;
  depositAmount?: number | null; balance_collected?: number;
};

const STATUS_MSG: Record<string, string> = {
  confirmed: "Booking confirmed",
  completed: "Booking completed",
  cancelled: "Booking cancelled",
  no_show: "Marked as no-show",
};

const PAYMENT_LABEL: Record<string, string> = {
  paid: "Paid", partially_refunded: "Partly refunded", refunded: "Refunded",
};
// Advance bookings: only `depositAmount` was paid online; the rest is paid at the venue.
const isAdvance = (b: Booking) => b.depositAmount != null;
const balanceDue = (b: Booking) =>
  isAdvance(b) && b.status !== "cancelled"
    ? Math.max(Math.round(((b.price ?? 0) - (b.depositAmount ?? 0) - (b.balance_collected ?? 0)) * 100) / 100, 0)
    : 0;
const isPaid = (b: { paymentStatus: string }) => b.paymentStatus === "paid" || b.paymentStatus === "partially_refunded";

const EMPTY_FILTER = { sport: "", status: "", date_from: "", date_to: "", deleted: "no" };
const PAGE_SIZE = 10;

type SortDir = "asc" | "desc";

function SortTh({
  col, label, sortBy, sortDir, onSort,
}: {
  col: string; label: string; sortBy: string; sortDir: SortDir;
  onSort: (col: string) => void;
}) {
  const active = sortBy === col;
  return (
    <th style={{ cursor: "pointer", userSelect: "none", whiteSpace: "nowrap" }}
      onClick={() => onSort(col)}>
      {label}{" "}
      {active
        ? (sortDir === "desc" ? "↓" : "↑")
        : <span style={{ opacity: 0.3 }}>↕</span>}
    </th>
  );
}

export function Bookings() {
  const toast = useToast();
  const confirm = useConfirm();
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("date");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [filter, setFilter] = useState(EMPTY_FILTER);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  function buildExportQuery() {
    const q = new URLSearchParams();
    if (filter.sport)     q.set("sport",     filter.sport);
    if (filter.status)    q.set("status",    filter.status);
    if (filter.date_from) q.set("date_from", filter.date_from);
    if (filter.date_to)   q.set("date_to",   filter.date_to);
    if (filter.deleted !== "no") q.set("deleted", filter.deleted);
    q.set("sort_by", sortBy);
    q.set("sort_dir", sortDir);
    return q;
  }

  useEffect(() => {
    const q = new URLSearchParams();
    if (filter.sport)     q.set("sport",     filter.sport);
    if (filter.status)    q.set("status",    filter.status);
    if (filter.date_from) q.set("date_from", filter.date_from);
    if (filter.date_to)   q.set("date_to",   filter.date_to);
    if (filter.deleted !== "no") q.set("deleted", filter.deleted);
    q.set("sort_by", sortBy);
    q.set("sort_dir", sortDir);
    q.set("limit",  String(PAGE_SIZE));
    q.set("offset", String((page - 1) * PAGE_SIZE));
    api.get<any>(`/admin/bookings?${q}`)
      .then((data) => {
        const items: Booking[] = Array.isArray(data) ? data : (data.items ?? []);
        const t: number = Array.isArray(data) ? data.length : (data.total ?? 0);
        setBookings(items);
        setTotal(t);
        setError("");
      })
      .catch((err) => setError(err.message ?? "Failed to load bookings"));
  }, [filter, sortBy, sortDir, page, reloadKey]);

  function handleSort(col: string) {
    setPage(1);
    if (sortBy === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
  }

  const [collectFor, setCollectFor] = useState<CollectTarget | null>(null);
  const [refundFor, setRefundFor] = useState<{ b: RefundTarget; mode: "cancel" | "refund" } | null>(null);

  function openRefund(b: Booking, mode: "cancel" | "refund") {
    setRefundFor({ b: { id: b.id, bookingRef: b.bookingRef, name: b.name, date: b.date, startTime: b.startTime }, mode });
  }

  async function setStatus(id: string, status: string) {
    try {
      await api.patch(`/admin/bookings/${id}`, { status });
      setReloadKey((k) => k + 1);
      toast.success(STATUS_MSG[status] ?? "Booking updated");
    } catch (err: any) {
      toast.error(err?.message ?? "Failed to update booking");
    }
  }

  async function exportCsv() {
    const q = buildExportQuery();
    try {
      // The API streams the CSV (every matching row, not just this page) and neutralises spreadsheet formulas.
      const { blob, filename } = await api.download(`/admin/bookings/export?${q}`);
      const url = URL.createObjectURL(blob);
      const a = Object.assign(document.createElement("a"), { href: url, download: filename });
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Export downloaded");
    } catch (err: any) {
      toast.error(err?.message ?? "Export failed");
    }
  }

  async function deleteBooking(b: Booking) {
    const ok = await confirm({
      message: `Delete booking ${b.bookingRef} (${b.name})? It disappears from the lists but stays in the records, and can be restored from "Deleted only".`,
      confirmLabel: "Delete", danger: true,
    });
    if (!ok) return;
    try {
      await api.delete(`/admin/bookings/${b.id}`);
      setReloadKey((k) => k + 1);
      toast.success("Booking deleted");
    } catch (err: any) {
      toast.error(err?.message ?? "Could not delete the booking");
    }
  }

  async function restoreBooking(b: Booking) {
    try {
      await api.post(`/admin/bookings/${b.id}/restore`, {});
      setReloadKey((k) => k + 1);
      toast.success("Booking restored");
    } catch (err: any) {
      toast.error(err?.message ?? "Could not restore the booking");
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const sortProps = { sortBy, sortDir, onSort: handleSort };

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Bookings" />
        <div className="page-body">
          <div className="filter-bar" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
            <select value={filter.sport} onChange={(e) => { setPage(1); setFilter((f) => ({ ...f, sport: e.target.value })); }}>
              <option value="">All sports</option>
              <option value="cricket">Cricket</option>
              <option value="football">Football</option>
              <option value="badminton">Badminton</option>
              <option value="pickleball">Pickleball</option>
            </select>
            <select data-testid="deleted-filter" value={filter.deleted} onChange={(e) => { setPage(1); setFilter((f) => ({ ...f, deleted: e.target.value })); }}>
              <option value="no">Hide deleted</option>
              <option value="only">Deleted only</option>
              <option value="all">Include deleted</option>
            </select>
            <select value={filter.status} onChange={(e) => { setPage(1); setFilter((f) => ({ ...f, status: e.target.value })); }}>
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="confirmed">Confirmed</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
              <option value="no_show">No-show</option>
            </select>
            <input
              type="date" title="From date"
              value={filter.date_from}
              onChange={(e) => { setPage(1); setFilter((f) => ({ ...f, date_from: e.target.value })); }}
            />
            <input
              type="date" title="To date"
              value={filter.date_to}
              onChange={(e) => { setPage(1); setFilter((f) => ({ ...f, date_to: e.target.value })); }}
            />
            {(filter.sport || filter.status || filter.date_from || filter.date_to || filter.deleted !== "no") && (
              <button className="btn-action secondary" onClick={() => { setPage(1); setFilter(EMPTY_FILTER); }}>Clear</button>
            )}
            <button
              className="btn-primary small"
              style={{ marginLeft: "auto" }}
              data-testid="export-csv"
              title="Download every booking matching these filters"
              onClick={exportCsv}
            >
              Export CSV
            </button>
          </div>

          {error ? (
            <p className="empty-msg" style={{ color: "var(--color-error, #f87171)" }}>{error}</p>
          ) : bookings.length === 0 ? (
            <p className="empty-msg">No bookings found.</p>
          ) : (
            <>
              <div className="table-wrap">
                <table className="bookings-table">
                  <colgroup>
                    <col style={{ width: 90 }} />   {/* Ref */}
                    <col style={{ width: 160 }} />  {/* Name */}
                    <col style={{ width: 85 }} />   {/* Sport */}
                    <col style={{ width: 105 }} />  {/* Date */}
                    <col style={{ width: 110 }} />  {/* Time */}
                    <col style={{ width: 65 }} />   {/* Players */}
                    <col style={{ width: 130 }} />  {/* Price */}
                    <col style={{ width: 65 }} />   {/* GST % */}
                    <col style={{ width: 110 }} />  {/* Status — sticky */}
                    <col style={{ width: 180 }} />  {/* Actions — sticky */}
                  </colgroup>
                  <thead>
                    <tr>
                      <th>Ref</th>
                      <SortTh col="name" label="Name" {...sortProps} />
                      <SortTh col="sportSlug" label="Sport" {...sortProps} />
                      <SortTh col="date" label="Date" {...sortProps} />
                      <th>Time</th>
                      <th>Plrs</th>
                      <SortTh col="price" label="Price" {...sortProps} />
                      <th>GST%</th>
                      <SortTh col="status" label="Status" {...sortProps} />
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bookings.map((b) => (
                      <tr key={b.id}>
                        <td><code title={b.bookingRef}>{b.bookingRef}</code></td>
                        <td>
                          <span className="cell-text" title={b.name}>{b.name}</span>
                          <small className="muted cell-text" title={b.contact}>{b.contact}</small>
                        </td>
                        <td style={{ textTransform: "capitalize" }}>{b.sportSlug}</td>
                        <td>{b.date}</td>
                        <td style={{ whiteSpace: "nowrap" }}>{b.startTime}–{b.endTime}</td>
                        <td>{b.party_size}</td>
                        <td title={b.promo_code ? `Promo: ${b.promo_code}` : undefined}>
                          {b.price != null ? `₹${b.price}` : "—"}
                          {b.promo_code && <small className="muted"> ({b.promo_code})</small>}
                          {isAdvance(b) && (
                            <small className="muted" data-testid={`advance-${b.bookingRef}`} style={{ display: "block", whiteSpace: "normal" }}>
                              Advance ₹{b.depositAmount}{balanceDue(b) > 0 ? ` · balance ₹${balanceDue(b)}` : b.status === "cancelled" ? "" : " · balance collected"}
                            </small>
                          )}
                        </td>
                        <td>{b.gst_rate_percent != null ? `${b.gst_rate_percent}%` : "—"}</td>
                        <td>
                          <StatusBadge status={b.status} />
                          {b.deleted_at && <small className="muted" data-testid={`deleted-${b.bookingRef}`} style={{ display: "block" }}>Deleted</small>}
                          {PAYMENT_LABEL[b.paymentStatus] && (
                            <small className="muted" data-testid={`pay-${b.bookingRef}`} style={{ display: "block" }}>
                              {PAYMENT_LABEL[b.paymentStatus]}
                            </small>
                          )}
                        </td>
                        <td>
                          <div className="action-row" style={{ whiteSpace: "nowrap" }}>
                            {b.deleted_at && (
                              <button className="btn-action confirm" data-testid={`restore-${b.bookingRef}`} onClick={() => restoreBooking(b)}>Restore</button>
                            )}
                            {!b.deleted_at && b.status === "pending" && (
                              <button className="btn-action confirm" onClick={() => setStatus(b.id, "confirmed")}>Confirm</button>
                            )}
                            {!b.deleted_at && b.status === "confirmed" && (
                              <button className="btn-action confirm" onClick={() => setStatus(b.id, "completed")}>Complete</button>
                            )}
                            {!b.deleted_at && b.status === "confirmed" && (
                              <button className="btn-action cancel" onClick={() => setStatus(b.id, "no_show")}>No-show</button>
                            )}
                            {!b.deleted_at && (b.status === "pending" || b.status === "confirmed") && (
                              // Paid bookings go through the refund dialog so a cancellation can never silently keep the money.
                              <button className="btn-action cancel" data-testid={`cancel-${b.bookingRef}`}
                                onClick={() => (isPaid(b) ? openRefund(b, "cancel") : setStatus(b.id, "cancelled"))}>Cancel</button>
                            )}
                            {!b.deleted_at && isPaid(b) && (b.status === "confirmed" || b.status === "completed") && balanceDue(b) > 0 && (
                              <button className="btn-action confirm" data-testid={`collect-${b.bookingRef}`}
                                onClick={() => setCollectFor({ id: b.id, bookingRef: b.bookingRef, name: b.name, balanceDue: balanceDue(b) })}>Collect balance</button>
                            )}
                            {!b.deleted_at && isPaid(b) && !isAdvance(b) && (
                              <button className="btn-action secondary" data-testid={`refund-${b.bookingRef}`}
                                onClick={() => openRefund(b, "refund")}>Refund</button>
                            )}
                            {!b.deleted_at && !isPaid(b) && ["cancelled", "completed", "no_show"].includes(b.status) && (
                              <button className="btn-action cancel" data-testid={`delete-${b.bookingRef}`} onClick={() => deleteBooking(b)}>Delete</button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="pagination-bar">
                <button disabled={page === 1} onClick={() => setPage((p) => p - 1)}>‹ Prev</button>
                <span>
                  {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}
                </span>
                <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next ›</button>
              </div>
            </>
          )}
        </div>
      </div>
      {collectFor && (
        <CollectBalanceDialog
          booking={collectFor}
          onClose={() => setCollectFor(null)}
          onDone={(message) => { setCollectFor(null); setReloadKey((k) => k + 1); toast.success(message); }}
        />
      )}
      {refundFor && (
        <RefundDialog
          booking={refundFor.b}
          mode={refundFor.mode}
          onClose={() => setRefundFor(null)}
          onDone={(message) => { setRefundFor(null); setReloadKey((k) => k + 1); toast.success(message); }}
        />
      )}
    </div>
  );
}
