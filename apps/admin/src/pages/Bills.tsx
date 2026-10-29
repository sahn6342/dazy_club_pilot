import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { SiteFooter } from "../components/SiteFooter";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import { DEFAULT_GST, dmy, gstValid, inr, previewTotals, type Bill, type DraftLine } from "../lib/bills";

const PAGE_SIZE = 10;
const EMPTY_LINE: DraftLine = { description: "", qty: "1", rate: "", gst: DEFAULT_GST };
const EMPTY_FILTER = { q: "", date_from: "", date_to: "", status: "" };

/** Create GST bills (item, rate, GST %) and find, reprint or void the old ones. */
export function Bills() {
  const nav = useNavigate();
  const toast = useToast();
  const [tab, setTab] = useState<"new" | "past">("new");

  // ── new bill ──
  const [lines, setLines] = useState<DraftLine[]>([{ ...EMPTY_LINE }]);
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerGstin, setCustomerGstin] = useState("");
  const [bookingRef, setBookingRef] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [tried, setTried] = useState(false);
  const calc = previewTotals(lines);
  const lineErr = (l: DraftLine) => ({
    desc: !l.description.trim(),
    qty: !(Number(l.qty) > 0),
    rate: l.rate.trim() === "" || !(Number(l.rate) >= 0),
    gst: !gstValid(l.gst),
  });
  const invalid = lines.some((l) => Object.values(lineErr(l)).some(Boolean)) || calc.total <= 0;

  function setLine(i: number, patch: Partial<DraftLine>) {
    setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  }

  async function save() {
    setTried(true);
    if (invalid || busy) return;
    setBusy(true);
    setError("");
    try {
      const bill = await api.post<Bill>("/admin/bills", {
        customerName: customerName.trim() || undefined, customerPhone: customerPhone.trim() || undefined,
        customerGstin: customerGstin.trim() || undefined, bookingRef: bookingRef.trim() || undefined,
        notes: notes.trim() || undefined,
        lines: lines.map((l) => ({ description: l.description.trim(), qty: Number(l.qty), rate: Number(l.rate), gstRatePercent: Number(l.gst) })),
      });
      toast.success(`Bill ${bill.billNo} saved`);
      nav(`/bills/${bill.id}/print?auto=1`);
    } catch (e: any) {
      setError(e?.message ?? "The bill could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  // ── past bills ──
  const [filter, setFilter] = useState(EMPTY_FILTER);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [bills, setBills] = useState<Bill[]>([]);
  const [total, setTotal] = useState(0);
  const [listError, setListError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [voiding, setVoiding] = useState<Bill | null>(null);
  const [reason, setReason] = useState("");
  const [voidBusy, setVoidBusy] = useState(false);
  const [voidError, setVoidError] = useState("");

  useEffect(() => { // debounce the search box
    const t = setTimeout(() => { setPage(1); setFilter((f) => ({ ...f, q: search })); }, 300);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    if (tab !== "past") return;
    const q = new URLSearchParams();
    (Object.keys(filter) as (keyof typeof filter)[]).forEach((k) => filter[k] && q.set(k, filter[k]));
    q.set("limit", String(PAGE_SIZE));
    q.set("offset", String((page - 1) * PAGE_SIZE));
    api.get<{ items: Bill[]; total: number }>(`/admin/bills?${q}`)
      .then((d) => { setBills(d.items); setTotal(d.total); setListError(""); })
      .catch((e) => setListError(e?.message ?? "Could not load bills"));
  }, [tab, filter, page, reloadKey]);

  async function voidBill() {
    if (!voiding || reason.trim().length < 3 || voidBusy) return;
    setVoidBusy(true);
    setVoidError("");
    try {
      await api.post(`/admin/bills/${voiding.id}/void`, { reason: reason.trim() });
      toast.success(`Bill ${voiding.billNo} voided`);
      setVoiding(null); setReason("");
      setReloadKey((k) => k + 1);
    } catch (e: any) {
      setVoidError(e?.message ?? "Could not void the bill");
    } finally {
      setVoidBusy(false);
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const input = { className: "cms-textarea", style: { width: "100%", padding: "0.4rem 0.55rem" } } as const;

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Bills" />
        <div className="page-body">
          <div className="tab-bar">
            <button className={`tab-btn${tab === "new" ? " active" : ""}`} data-testid="tab-new" onClick={() => setTab("new")}>New bill</button>
            <button className={`tab-btn${tab === "past" ? " active" : ""}`} data-testid="tab-past" onClick={() => setTab("past")}>Past bills</button>
          </div>

          {tab === "new" ? (
            <div data-testid="bill-form">
              <div className="table-wrap">
                <table className="bills-lines">
                  <thead>
                    <tr><th>#</th><th>Item</th><th>Qty</th><th>Rate ₹ (incl. GST)</th><th>GST %</th><th>Amount</th><th /></tr>
                  </thead>
                  <tbody>
                    {lines.map((l, i) => (
                      <tr key={i} data-testid={`line-${i}`}>
                        <td>{i + 1}</td>
                        <td style={{ minWidth: 200 }}>
                          <input {...input} data-testid={`line-desc-${i}`} maxLength={200} value={l.description}
                            onChange={(e) => setLine(i, { description: e.target.value })} />
                          {tried && lineErr(l).desc && <span className="field-error">Item needed</span>}
                        </td>
                        <td style={{ width: 90 }}>
                          <input {...input} data-testid={`line-qty-${i}`} type="number" min="0" step="any" value={l.qty}
                            onChange={(e) => setLine(i, { qty: e.target.value })} />
                          {tried && lineErr(l).qty && <span className="field-error">Qty &gt; 0</span>}
                        </td>
                        <td style={{ width: 140 }}>
                          <input {...input} data-testid={`line-rate-${i}`} type="number" min="0" step="0.01" value={l.rate}
                            onChange={(e) => setLine(i, { rate: e.target.value })} />
                          {tried && lineErr(l).rate && <span className="field-error">Rate needed</span>}
                        </td>
                        <td style={{ width: 90 }}>
                          <input {...input} data-testid={`line-gst-${i}`} type="number" min="0" max="28" step="0.01" value={l.gst}
                            onChange={(e) => setLine(i, { gst: e.target.value })} />
                          {tried && lineErr(l).gst && <span className="field-error">0–28</span>}
                        </td>
                        <td data-testid={`line-total-${i}`} style={{ whiteSpace: "nowrap", textAlign: "right" }}>{inr(calc.rows[i].total)}</td>
                        <td>
                          <button className="btn-action cancel" data-testid={`line-remove-${i}`} disabled={lines.length === 1}
                            title="Remove this row" onClick={() => setLines((ls) => ls.filter((_, j) => j !== i))}>✕</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button className="btn-action secondary" data-testid="add-row" style={{ margin: "0.5rem 0 1rem" }}
                disabled={lines.length >= 50} onClick={() => setLines((ls) => [...ls, { ...EMPTY_LINE }])}>+ Add row</button>

              <div className="bills-grid">
                <div className="bills-customer">
                  <label className="field-group">Customer name (optional)
                    <input {...input} data-testid="bill-name" maxLength={80} value={customerName} onChange={(e) => setCustomerName(e.target.value)} />
                  </label>
                  <label className="field-group">Phone (optional)
                    <input {...input} data-testid="bill-phone" inputMode="tel" maxLength={10} value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} />
                  </label>
                  <label className="field-group">Customer GSTIN (optional)
                    <input {...input} data-testid="bill-gstin" maxLength={15} value={customerGstin} onChange={(e) => setCustomerGstin(e.target.value.toUpperCase())} />
                  </label>
                  <label className="field-group">Booking ref (optional)
                    <input {...input} data-testid="bill-booking" maxLength={20} value={bookingRef} onChange={(e) => setBookingRef(e.target.value.toUpperCase())} />
                  </label>
                  <label className="field-group">Notes (printed on the bill)
                    <textarea {...input} data-testid="bill-notes" maxLength={500} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
                  </label>
                </div>
                <div className="bills-totals" data-testid="bill-totals">
                  <div><span>Taxable value</span><b data-testid="sum-taxable">{inr(calc.taxable)}</b></div>
                  <div><span>CGST</span><b data-testid="sum-cgst">{inr(calc.cgst)}</b></div>
                  <div><span>SGST</span><b data-testid="sum-sgst">{inr(calc.sgst)}</b></div>
                  <div className="grand"><span>Total (incl. GST)</span><b data-testid="sum-total">{inr(calc.total)}</b></div>
                  {error && <p className="field-error" data-testid="bill-error">{error}</p>}
                  {tried && calc.total <= 0 && <p className="field-error">The bill total must be more than zero.</p>}
                  <button className="btn-primary" data-testid="save-print" disabled={busy} onClick={save}>
                    {busy ? "Saving…" : "Save & print"}
                  </button>
                  <small className="muted">The bill gets its number when saved. It cannot be edited afterwards, only voided.</small>
                </div>
              </div>
            </div>
          ) : (
            <div data-testid="bill-list">
              <div className="filter-bar" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
                <input data-testid="bill-search" placeholder="Search bill no, name or phone" value={search} onChange={(e) => setSearch(e.target.value)} />
                <input type="date" title="From date" value={filter.date_from} onChange={(e) => { setPage(1); setFilter((f) => ({ ...f, date_from: e.target.value })); }} />
                <input type="date" title="To date" value={filter.date_to} onChange={(e) => { setPage(1); setFilter((f) => ({ ...f, date_to: e.target.value })); }} />
                <select data-testid="bill-status" value={filter.status} onChange={(e) => { setPage(1); setFilter((f) => ({ ...f, status: e.target.value })); }}>
                  <option value="">All bills</option><option value="active">Active</option><option value="void">Void</option>
                </select>
              </div>
              {listError ? <p className="empty-msg" style={{ color: "#f87171" }}>{listError}</p>
                : bills.length === 0 ? <p className="empty-msg">No bills found.</p>
                : (
                  <>
                    <div className="table-wrap">
                      <table className="bookings-table">
                        <thead><tr><th>Bill no</th><th>Date</th><th>Customer</th><th style={{ textAlign: "right" }}>Total</th><th>Status</th><th>Actions</th></tr></thead>
                        <tbody>
                          {bills.map((b) => (
                            <tr key={b.id} data-testid={`bill-row-${b.billNo}`}>
                              <td><code>{b.billNo}</code></td>
                              <td>{dmy(b.billDate)}</td>
                              <td>
                                <span className="cell-text">{b.customerName ?? "—"}</span>
                                {b.customerPhone && <small className="muted cell-text">{b.customerPhone}</small>}
                              </td>
                              <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>{inr(b.total)}</td>
                              <td>
                                {b.status === "void"
                                  ? <span title={b.voidReason ?? ""} className="bill-void-tag">Void</span>
                                  : <span className="muted">Active</span>}
                              </td>
                              <td>
                                <div className="action-row" style={{ whiteSpace: "nowrap" }}>
                                  <Link className="btn-action confirm" data-testid={`reprint-${b.billNo}`} to={`/bills/${b.id}/print?auto=1`}>Reprint</Link>
                                  <Link className="btn-action secondary" to={`/bills/${b.id}/print`}>View</Link>
                                  {b.status === "active" && (
                                    <button className="btn-action cancel" data-testid={`void-${b.billNo}`} onClick={() => { setVoiding(b); setReason(""); setVoidError(""); }}>Void</button>
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
                      <span>{(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}</span>
                      <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next ›</button>
                    </div>
                  </>
                )}
            </div>
          )}
        </div>
        <SiteFooter />
      </div>

      {voiding && (
        <div className="confirm-overlay" role="dialog" aria-modal="true" data-testid="void-dialog"
          onClick={(e) => { if (e.target === e.currentTarget && !voidBusy) setVoiding(null); }}>
          <div className="confirm-dialog" style={{ maxWidth: 420, textAlign: "left" }}>
            <h3 style={{ margin: "0 0 0.25rem" }}>Void bill {voiding.billNo}?</h3>
            <p className="muted" style={{ fontSize: "0.85rem" }}>
              {inr(voiding.total)} · the bill stays in the records marked VOID and its number is not reused.
            </p>
            <label style={{ display: "block", fontSize: "0.85rem" }}>Reason
              <input data-testid="void-reason" className="cms-textarea" maxLength={200} value={reason} onChange={(e) => setReason(e.target.value)}
                style={{ display: "block", width: "100%", marginTop: "0.25rem", padding: "0.45rem 0.65rem" }} />
            </label>
            {voidError && <p className="field-error">{voidError}</p>}
            <div className="confirm-actions" style={{ marginTop: "1rem" }}>
              <button className="btn-action secondary" onClick={() => setVoiding(null)} disabled={voidBusy}>Keep bill</button>
              <button className="btn-action cancel" data-testid="void-confirm" disabled={voidBusy || reason.trim().length < 3} onClick={voidBill}>
                {voidBusy ? "Voiding…" : "Void bill"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
