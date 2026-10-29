export type BillLine = {
  position: number; description: string; qty: number; rate: number; gstRatePercent: number;
  taxableValue: number; cgst: number; sgst: number; lineTotal: number;
};

export type Bill = {
  id: string; billNo: string; billDate: string; customerName: string | null; customerPhone: string | null;
  customerGstin: string | null; notes: string | null; bookingRef: string | null;
  /** true: the rates on the bill include GST. false: older bills, whose rates were before GST. */
  pricesIncludeTax: boolean;
  taxableValue: number; cgst: number; sgst: number; roundOff: number; total: number; amountInWords: string;
  status: "active" | "void"; voidReason: string | null; voidedAt: string | null; createdBy: string; createdAt: string;
  lines?: BillLine[];
};

export type Business = {
  name: string; gstin: string | null; address: string | null; phone: string | null; email: string | null; title: string;
};

export const DEFAULT_GST = "18";

export const inr = (n: number) =>
  `₹${n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/** 2026-10-28 -> 28-10-2026 */
export const dmy = (iso: string) => iso.split("-").reverse().join("-");

const paise = (x: number) => Math.round((x + Number.EPSILON) * 100);

export type DraftLine = { description: string; qty: string; rate: string; gst: string };

export const gstValid = (gst: string) => gst.trim() !== "" && Number(gst) >= 0 && Number(gst) <= 28;

/**
 * Live preview of the bill while it is typed. The rate includes GST, so a row's amount is qty x rate and the tax is
 * backed out of it. The server recomputes every figure when the bill is saved and that result is what gets printed;
 * this mirrors its rules (CGST = SGST, rounded down to the paisa; total is the sum of the rows, not rounded) so the
 * two agree to the paisa.
 */
export function previewTotals(lines: DraftLine[]) {
  let taxable = 0, cgst = 0, total = 0;
  const rows = lines.map((l) => {
    const qty = Number(l.qty), rate = Number(l.rate);
    const ok = l.qty.trim() !== "" && l.rate.trim() !== "" && qty > 0 && rate >= 0 && gstValid(l.gst);
    if (!ok) return { taxable: 0, cgst: 0, total: 0, ok };
    const pct = Math.round(Number(l.gst) * 100) / 100;
    const amount = paise(qty * rate);
    const gst = amount - Math.round((amount * 100) / (100 + pct));
    const half = Math.floor(gst / 2);
    taxable += amount - 2 * half; cgst += half; total += amount;
    return { taxable: (amount - 2 * half) / 100, cgst: half / 100, total: amount / 100, ok };
  });
  return { rows, taxable: taxable / 100, cgst: cgst / 100, sgst: cgst / 100, gst: (2 * cgst) / 100, total: total / 100 };
}
