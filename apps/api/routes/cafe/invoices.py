from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from auth import get_current_admin, get_current_cashier
from deps import invoice_repo, cafe_settings_repo, order_repo, payment_repo
from models import InvoiceDto, InvoiceLineDto

router = APIRouter()


def _invoice_dto(invoice_id: str) -> InvoiceDto:
    inv = invoice_repo.get_by_id(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    lines = invoice_repo.get_lines(invoice_id)
    dto = InvoiceDto.model_validate(inv)
    dto.lines = [InvoiceLineDto.model_validate(l) for l in lines]
    return dto


@router.get("/cafe/invoices/{invoice_id}", response_model=InvoiceDto)
def get_invoice(invoice_id: str, _=Depends(get_current_cashier)):
    return _invoice_dto(invoice_id)


@router.get("/cafe/invoices/{invoice_id}/print", response_class=HTMLResponse)
def print_invoice(invoice_id: str):
    inv = invoice_repo.get_by_id(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    lines = invoice_repo.get_lines(invoice_id)
    settings = cafe_settings_repo.get()
    order = order_repo.get_by_id(inv.order_id)
    payments = payment_repo.get_by_order(inv.order_id) if order else []

    # ── Business info ──
    biz_name = settings.legalName or "Dazy.club Cafe"
    gstin = settings.gstin or ""
    fssai = settings.fssaiNumber or ""
    address = settings.addressLine or ""
    city = settings.city or ""
    footer_note = settings.footerNote or "Thank you! Visit again."

    # ── Line items HTML ──
    lines_html = ""
    for ln in lines:
        lines_html += f"""
        <tr>
          <td>{ln.description}</td>
          <td class="r">{float(ln.qty):.2f}</td>
          <td class="r">{float(ln.rate):.2f}</td>
          <td class="r">{float(ln.gstRatePercent):.0f}%</td>
          <td class="r">{float(ln.lineTotal):.2f}</td>
        </tr>"""

    # ── GST rate-wise summary ──
    rate_buckets: dict[float, dict] = defaultdict(lambda: {"taxable": 0.0, "cgst": 0.0, "sgst": 0.0})
    for ln in lines:
        rate = float(ln.gstRatePercent)
        rate_buckets[rate]["taxable"] += float(ln.taxableValue)
        rate_buckets[rate]["cgst"] += float(ln.cgst)
        rate_buckets[rate]["sgst"] += float(ln.sgst)

    gst_rows_html = ""
    for rate, vals in sorted(rate_buckets.items()):
        gst_rows_html += f"""
        <tr>
          <td>GST {rate:.0f}%</td>
          <td class="r">{vals['taxable']:.2f}</td>
          <td class="r">{vals['cgst']:.2f}</td>
          <td class="r">{vals['sgst']:.2f}</td>
        </tr>"""

    # ── Payments HTML ──
    payments_html = ""
    for p in payments:
        payments_html += f"<div class='row'><span>{p.mode.upper()}</span><span>&#8377;{float(p.amount):.2f}</span></div>"

    order_no = order.orderNo if order else inv.order_id
    issued_date = inv.issuedAt[:10] if inv.issuedAt else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Invoice {inv.invoiceNo}</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: 'Courier New', monospace;
      font-size: 10px;
      width: 58mm;
      padding: 4px;
      color: #000;
      background: #fff;
    }}
    h1 {{ font-size: 13px; text-align: center; margin-bottom: 2px; }}
    .center {{ text-align: center; }}
    .sep {{ border-top: 1px dashed #000; margin: 4px 0; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 1px 0; vertical-align: top; }}
    th {{ font-size: 9px; border-bottom: 1px solid #000; }}
    .r {{ text-align: right; }}
    .row {{ display: flex; justify-content: space-between; }}
    .bold {{ font-weight: bold; }}
    .total-row {{ font-size: 11px; font-weight: bold; }}
    @media print {{
      body {{ width: 58mm; }}
      @page {{ size: 80mm auto; margin: 0; }}
    }}
  </style>
</head>
<body>
  <h1>{biz_name}</h1>
  {'<p class="center">GSTIN: ' + gstin + '</p>' if gstin else ''}
  {'<p class="center">FSSAI: ' + fssai + '</p>' if fssai else ''}
  <p class="center">{address}{', ' + city if city else ''}</p>
  <div class="sep"></div>
  <p class="center bold">{inv.invoiceType.replace('_', ' ').upper()}</p>
  <div class="row"><span>Invoice#: {inv.invoiceNo}</span></div>
  <div class="row"><span>Date: {issued_date}</span><span>Order: {order_no}</span></div>
  <div class="sep"></div>

  <table>
    <thead>
      <tr>
        <th>Item</th><th class="r">Qty</th><th class="r">Rate</th><th class="r">GST</th><th class="r">Total</th>
      </tr>
    </thead>
    <tbody>{lines_html}</tbody>
  </table>
  <div class="sep"></div>

  <div class="row"><span>Taxable Value</span><span>&#8377;{float(inv.taxableValue):.2f}</span></div>
  <div class="row"><span>CGST</span><span>&#8377;{float(inv.cgst):.2f}</span></div>
  <div class="row"><span>SGST</span><span>&#8377;{float(inv.sgst):.2f}</span></div>
  {'<div class="row"><span>Round Off</span><span>&#8377;' + f"{float(inv.roundOff):.2f}" + '</span></div>' if inv.roundOff != 0 else ''}
  <div class="sep"></div>
  <div class="row total-row"><span>TOTAL</span><span>&#8377;{float(inv.total):.2f}</span></div>
  <p style="font-size:9px">{inv.amountInWords}</p>
  <div class="sep"></div>

  <p class="bold">GST Summary</p>
  <table>
    <thead>
      <tr><th>Rate</th><th class="r">Taxable</th><th class="r">CGST</th><th class="r">SGST</th></tr>
    </thead>
    <tbody>{gst_rows_html}</tbody>
  </table>
  <div class="sep"></div>

  <p class="bold">Payment</p>
  {payments_html}
  <div class="sep"></div>
  <p class="center">{footer_note}</p>

  <script>window.onload = () => window.print();</script>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.get("/cafe/invoices", response_model=list[InvoiceDto])
def list_invoices(order_id: str | None = None, _=Depends(get_current_admin)):
    rows = invoice_repo.get_all(order_id=order_id)
    result = []
    for row in rows:
        lines = invoice_repo.get_lines(row.id)
        dto = InvoiceDto.model_validate(row)
        dto.lines = [InvoiceLineDto.model_validate(l) for l in lines]
        result.append(dto)
    return result
