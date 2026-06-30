import { useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";

type Settings = {
  legalName: string; gstin: string; fssaiNumber: string;
  addressLine: string; city: string; stateName: string; stateCode: string;
  scheme: string; priceIncludesTax: boolean; defaultTaxRate: number;
  invoiceSeriesPrefix: string; billOfSupplySeriesPrefix: string;
  declaration: string; footerNote: string; roundingEnabled: boolean;
};

const SCHEME_OPTS = ["regular", "composition", "unregistered"];

const DEFAULTS: Settings = {
  legalName: "", gstin: "", fssaiNumber: "",
  addressLine: "", city: "", stateName: "", stateCode: "",
  scheme: "regular", priceIncludesTax: true, defaultTaxRate: 5,
  invoiceSeriesPrefix: "INV", billOfSupplySeriesPrefix: "BOS",
  declaration: "", footerNote: "", roundingEnabled: true,
};

export function CafeSettings() {
  const toast = useToast();
  const [form, setForm] = useState<Settings>(DEFAULTS);
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState("");

  useEffect(() => {
    api.get<any>("/admin/cafe/settings").then((s) => setForm({
      legalName: s.legalName ?? "",
      gstin: s.gstin ?? "",
      fssaiNumber: s.fssaiNumber ?? "",
      addressLine: s.addressLine ?? "",
      city: s.city ?? "",
      stateName: s.stateName ?? "",
      stateCode: s.stateCode ?? "",
      scheme: s.scheme ?? "regular",
      priceIncludesTax: s.priceIncludesTax ?? true,
      defaultTaxRate: s.defaultTaxRate ?? 5,
      invoiceSeriesPrefix: s.invoiceSeriesPrefix ?? "INV",
      billOfSupplySeriesPrefix: s.billOfSupplySeriesPrefix ?? "BOS",
      declaration: s.declaration ?? "",
      footerNote: s.footerNote ?? "",
      roundingEnabled: s.roundingEnabled ?? true,
    })).catch(() => {});
  }, []);

  const set = (key: keyof Settings) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setServerError("");
    const payload = {
      legalName: form.legalName || null,
      gstin: form.gstin || null,
      fssaiNumber: form.fssaiNumber || null,
      addressLine: form.addressLine || null,
      city: form.city || null,
      stateName: form.stateName || null,
      stateCode: form.stateCode || null,
      scheme: form.scheme,
      priceIncludesTax: form.priceIncludesTax,
      defaultTaxRate: form.defaultTaxRate,
      invoiceSeriesPrefix: form.invoiceSeriesPrefix || "INV",
      billOfSupplySeriesPrefix: form.billOfSupplySeriesPrefix || "BOS",
      declaration: form.declaration || null,
      footerNote: form.footerNote || null,
      roundingEnabled: form.roundingEnabled,
    };
    try {
      await api.put("/admin/cafe/settings", payload);
      toast.success("Settings saved");
    } catch (err: any) {
      setServerError(err?.message ?? "Failed");
      toast.error(err?.message ?? "Failed");
    } finally {
      setSaving(false);
    }
  }

  const inputStyle = { padding: "0.55rem 0.75rem", borderRadius: "8px", fontFamily: "inherit" } as const;

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Café Settings" />
        <div className="page-body">
          <form className="user-form" onSubmit={handleSubmit} noValidate style={{ maxWidth: "640px" }}>

            <h3 className="section-heading">Business info</h3>

            <div className="field-group">
              <label className="cms-label">Legal name
                <input className="cms-textarea" style={inputStyle} value={form.legalName} onChange={set("legalName")} placeholder="Your café's registered legal name" />
              </label>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
              <div className="field-group">
                <label className="cms-label">GSTIN
                  <input className="cms-textarea" style={inputStyle} value={form.gstin} onChange={set("gstin")} placeholder="22AAAAA0000A1Z5" />
                </label>
              </div>
              <div className="field-group">
                <label className="cms-label">FSSAI number
                  <input className="cms-textarea" style={inputStyle} value={form.fssaiNumber} onChange={set("fssaiNumber")} placeholder="14-digit FSSAI" />
                </label>
              </div>
            </div>
            <div className="field-group">
              <label className="cms-label">Address line
                <input className="cms-textarea" style={inputStyle} value={form.addressLine} onChange={set("addressLine")} placeholder="Street / building" />
              </label>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: "0.75rem" }}>
              <div className="field-group">
                <label className="cms-label">City
                  <input className="cms-textarea" style={inputStyle} value={form.city} onChange={set("city")} placeholder="Hyderabad" />
                </label>
              </div>
              <div className="field-group">
                <label className="cms-label">State name
                  <input className="cms-textarea" style={inputStyle} value={form.stateName} onChange={set("stateName")} placeholder="Telangana" />
                </label>
              </div>
              <div className="field-group">
                <label className="cms-label">State code
                  <input className="cms-textarea" style={inputStyle} value={form.stateCode} onChange={set("stateCode")} placeholder="36" />
                </label>
              </div>
            </div>

            <h3 className="section-heading" style={{ marginTop: "1.75rem" }}>Tax</h3>

            <div className="field-group">
              <label className="cms-label">GST scheme</label>
              <div className="role-selector">
                {SCHEME_OPTS.map((s) => (
                  <button key={s} type="button"
                    className={`role-option${form.scheme === s ? " active" : ""}`}
                    onClick={() => setForm((f) => ({ ...f, scheme: s }))}
                  >{s}</button>
                ))}
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
              <div className="field-group">
                <label className="cms-label">Default tax rate %
                  <input type="number" min="0" max="100" step="0.5" className="cms-textarea" style={inputStyle}
                    value={form.defaultTaxRate}
                    onChange={(e) => setForm((f) => ({ ...f, defaultTaxRate: Number(e.target.value) }))}
                  />
                </label>
              </div>
              <div className="field-group" style={{ display: "flex", alignItems: "flex-end", paddingBottom: "0.25rem" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                  <input type="checkbox" checked={form.priceIncludesTax}
                    onChange={(e) => setForm((f) => ({ ...f, priceIncludesTax: e.target.checked }))} />
                  <span className="cms-label" style={{ margin: 0 }}>Price includes tax</span>
                </label>
              </div>
            </div>

            <h3 className="section-heading" style={{ marginTop: "1.75rem" }}>Invoicing</h3>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
              <div className="field-group">
                <label className="cms-label">Invoice prefix
                  <input className="cms-textarea" style={inputStyle} value={form.invoiceSeriesPrefix} onChange={set("invoiceSeriesPrefix")} placeholder="INV" />
                </label>
              </div>
              <div className="field-group">
                <label className="cms-label">Bill of supply prefix
                  <input className="cms-textarea" style={inputStyle} value={form.billOfSupplySeriesPrefix} onChange={set("billOfSupplySeriesPrefix")} placeholder="BOS" />
                </label>
              </div>
            </div>
            <div className="field-group">
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                <input type="checkbox" checked={form.roundingEnabled}
                  onChange={(e) => setForm((f) => ({ ...f, roundingEnabled: e.target.checked }))} />
                <span className="cms-label" style={{ margin: 0 }}>Enable amount rounding</span>
              </label>
            </div>

            <h3 className="section-heading" style={{ marginTop: "1.75rem" }}>Receipt content</h3>

            <div className="field-group">
              <label className="cms-label">Declaration
                <textarea className="cms-textarea" style={{ ...inputStyle, minHeight: "80px", resize: "vertical" }}
                  value={form.declaration}
                  onChange={set("declaration")}
                  placeholder="Declaration text printed on invoices"
                />
              </label>
            </div>
            <div className="field-group">
              <label className="cms-label">Footer note
                <input className="cms-textarea" style={inputStyle} value={form.footerNote} onChange={set("footerNote")} placeholder="e.g. Thank you for visiting!" />
              </label>
            </div>

            {serverError && <p className="error-msg">{serverError}</p>}
            <button className="btn-primary" type="submit" disabled={saving} style={{ marginTop: "0.5rem" }}>
              {saving ? "Saving…" : "Save settings"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
