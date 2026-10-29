import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { dmy, inr, type Bill, type Business } from "../lib/bills";

const store = {
  get(key: string, fallback: string) { try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; } },
  set(key: string, value: string) { try { localStorage.setItem(key, value); } catch { /* private mode: setting just is not remembered */ } },
};

/** One bill on an A4 sheet. Opens with the print dialog when reached with ?auto=1 (save & print, reprint). */
export function BillPrint() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const [bill, setBill] = useState<Bill | null>(null);
  const [biz, setBiz] = useState<Business | null>(null);
  const [error, setError] = useState("");
  // For pre-printed letterhead paper: leave the header off and push the bill below the printed one.
  const [showHeader, setShowHeader] = useState(() => store.get("dazy_bill_header", "1") === "1");
  const [topMm, setTopMm] = useState(() => store.get("dazy_bill_top_mm", "0"));
  const top = Math.min(Math.max(Number(topMm) || 0, 0), 120);

  useEffect(() => {
    Promise.all([api.get<Bill>(`/admin/bills/${id}`), api.get<Business>("/admin/bills/business")])
      .then(([b, c]) => { setBill(b); setBiz(c); })
      .catch((e) => setError(e?.message ?? "Could not load the bill"));
  }, [id]);

  const ready = bill && biz;
  useEffect(() => {
    if (!ready || params.get("auto") !== "1") return;
    const t = setTimeout(() => window.print(), 400); // let the logo and fonts settle first
    return () => clearTimeout(t);
  }, [ready, params]);

  if (error) return <div className="bill-page"><p className="field-error" data-testid="print-error">{error}</p><Link to="/bills">← Bills</Link></div>;
  if (!bill || !biz) return <div className="bill-page"><p className="muted">Loading bill…</p></div>;

  const lines = bill.lines ?? [];
  return (
    <div className="bill-page">
      <div className="bill-toolbar no-print">
        <Link to="/bills" className="btn-action secondary">← Bills</Link>
        <label><input type="checkbox" data-testid="print-header" checked={showHeader}
          onChange={(e) => { setShowHeader(e.target.checked); store.set("dazy_bill_header", e.target.checked ? "1" : "0"); }} /> Print letterhead</label>
        <label title="Space left at the top of the page, for paper that already has a printed letterhead">Top space (mm)
          <input type="number" min={0} max={120} data-testid="print-top" value={topMm}
            onChange={(e) => { setTopMm(e.target.value); store.set("dazy_bill_top_mm", e.target.value); }} style={{ width: 70, marginLeft: 6 }} />
        </label>
        <button className="btn-primary small" data-testid="print-now" onClick={() => window.print()}>Print (A4)</button>
      </div>

      <div className="bill-sheet" data-testid="bill-sheet" style={{ paddingTop: `${top}mm` }}>
        {bill.status === "void" && <div className="bill-watermark" data-testid="void-mark">VOID</div>}

        {showHeader && (
          <header className="bill-head">
            <img src="/logo.webp" alt="" className="bill-logo" />
            <div className="bill-biz">
              <h1>{biz.name}</h1>
              {biz.address && <p>{biz.address}</p>}
              {biz.phone && <p>Ph: {biz.phone}</p>}
              {biz.email && <p>Email: {biz.email}</p>}
              {biz.gstin && <p><b>GSTIN: {biz.gstin}</b></p>}
            </div>
          </header>
        )}

        <div className="bill-meta">
          <h2 data-testid="print-title">{biz.title}</h2>
          <div>
            <div>Bill no: <b data-testid="print-billno">{bill.billNo}</b></div>
            <div>Date: <b>{dmy(bill.billDate)}</b></div>
            {bill.bookingRef && <div>Booking: {bill.bookingRef}</div>}
          </div>
        </div>

        {(bill.customerName || bill.customerPhone || bill.customerGstin) && (
          <div className="bill-to">
            <span>Billed to</span>
            <b>{bill.customerName ?? ""}</b>
            {bill.customerPhone && <span>{bill.customerPhone}</span>}
            {bill.customerGstin && <span>GSTIN: {bill.customerGstin}</span>}
          </div>
        )}

        <table className="bill-table">
          <thead>
            <tr>
              <th>#</th><th className="l">Description</th><th>Qty</th><th>{bill.pricesIncludeTax ? "Rate (incl. GST)" : "Rate (excl. GST)"}</th><th>Taxable</th>
              <th>GST %</th><th>CGST</th><th>SGST</th><th>Amount</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((l) => (
              <tr key={l.position}>
                <td>{l.position}</td>
                <td className="l">{l.description}</td>
                <td>{l.qty}</td>
                <td>{l.rate.toFixed(2)}</td>
                <td>{l.taxableValue.toFixed(2)}</td>
                <td>{l.gstRatePercent}%</td>
                <td>{l.cgst.toFixed(2)}</td>
                <td>{l.sgst.toFixed(2)}</td>
                <td>{l.lineTotal.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="bill-sum">
          <div><span>Taxable value</span><span>{inr(bill.taxableValue)}</span></div>
          <div><span>CGST</span><span>{inr(bill.cgst)}</span></div>
          <div><span>SGST</span><span>{inr(bill.sgst)}</span></div>
          {bill.roundOff !== 0 && <div><span>Round off</span><span>{bill.roundOff < 0 ? "-" : ""}{inr(Math.abs(bill.roundOff))}</span></div>}
          <div className="grand"><span>Total</span><span data-testid="print-total">{inr(bill.total)}</span></div>
        </div>
        <p className="bill-words"><b>Amount in words:</b> {bill.amountInWords}</p>

        {bill.notes && <p className="bill-notes"><b>Note:</b> {bill.notes}</p>}
        {bill.status === "void" && <p className="bill-notes"><b>Void:</b> {bill.voidReason}</p>}
        <div className="bill-sign"><span>Authorised signatory</span></div>
      </div>
    </div>
  );
}
