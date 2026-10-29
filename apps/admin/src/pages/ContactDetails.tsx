import { useEffect, useState } from "react";
import { BRAND } from "@dazy/shared";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import { SiteFooter } from "../components/SiteFooter";

type CmsEntry = { key: string; label: string; value: string };

const VENUE_KEYS = [
  "venue_name",
  "venue_address",
  "venue_phone",
  "venue_email",
  "venue_gstin",
  "venue_hours",
  "social_instagram",
  "social_facebook",
  "whatsapp_phone",
  "whatsapp_message",
  "booking_gst_rate",
  "booking_advance_amount",
];

const inputStyle: React.CSSProperties = {
  padding: "0.5rem 0.65rem",
  borderRadius: "8px",
  fontFamily: "inherit",
  width: "100%",
};

export function ContactDetails() {
  const toast = useToast();
  const [entries, setEntries] = useState<CmsEntry[]>([]);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function load() {
    api.get<CmsEntry[]>("/admin/cms").then((data) => {
      const venue = data.filter((e) => VENUE_KEYS.includes(e.key));
      setEntries(venue);
      setVals(Object.fromEntries(venue.map((e) => [e.key, e.value])));
    }).catch((e) => setError(e.message));
  }

  useEffect(() => { load(); }, []);

  async function saveAll(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await Promise.all(
        entries.map((en) =>
          api.put(`/admin/cms/${en.key}`, { value: vals[en.key] ?? "", label: en.label })
        )
      );
      toast.success("Contact details saved");
      load();
    } catch (err: any) {
      const msg = err?.message ?? "Failed to save";
      setError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  const fieldMeta: Record<string, { label: string; placeholder: string; multiline?: boolean }> = {
    venue_name:        { label: "Venue name",         placeholder: `e.g. ${BRAND.name}` },
    venue_address:     { label: "Address",            placeholder: "Full address", multiline: true },
    venue_phone:       { label: "Phone",              placeholder: "+91 98765 43210" },
    venue_email:       { label: "Email",              placeholder: "dazyclub1223@gmail.com" },
    venue_gstin:       { label: "GSTIN (printed on bills; leave empty if not registered)", placeholder: "10ABCDE1234F1Z5" },
    venue_hours:       { label: "Opening hours",      placeholder: "Mon–Sun: 6 AM – 9 PM", multiline: true },
    social_instagram:  { label: "Instagram URL",      placeholder: "https://instagram.com/..." },
    social_facebook:   { label: "Facebook URL",       placeholder: "https://facebook.com/..." },
    whatsapp_phone:    { label: "WhatsApp phone (country code + digits only)", placeholder: "919876543211" },
    whatsapp_message:  { label: "WhatsApp pre-filled message", placeholder: "Hello! I am interested.", multiline: true },
    booking_gst_rate:  { label: "Slot booking GST rate (%)", placeholder: "18" },
    booking_advance_amount: { label: "Advance payment (₹, non-refundable; 0 = customers must pay in full)", placeholder: "500" },
  };

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Contact Details" />
        <div className="page-body">
          {error && <p className="error-msg">{error}</p>}
          <form className="user-form" onSubmit={saveAll} style={{ maxWidth: 640 }}>
            <p className="muted" style={{ marginBottom: "1.5rem" }}>
              These details appear on the public Contact page. Changes take effect immediately.
            </p>
            {entries.length === 0 && !error && (
              <p className="muted">Loading…</p>
            )}
            {VENUE_KEYS.filter((k) => entries.find((e) => e.key === k)).map((key) => {
              const meta = fieldMeta[key];
              return (
                <div key={key} className="field-group" style={{ marginBottom: "1rem" }}>
                  <label className="cms-label">
                    {meta?.label ?? key}
                    {meta?.multiline ? (
                      <textarea
                        className="cms-textarea"
                        style={inputStyle}
                        rows={3}
                        value={vals[key] ?? ""}
                        placeholder={meta?.placeholder}
                        onChange={(e) => setVals((v) => ({ ...v, [key]: e.target.value }))}
                      />
                    ) : (
                      <input
                        className="cms-textarea"
                        style={inputStyle}
                        value={vals[key] ?? ""}
                        placeholder={meta?.placeholder}
                        onChange={(e) => setVals((v) => ({ ...v, [key]: e.target.value }))}
                      />
                    )}
                  </label>
                </div>
              );
            })}
            {entries.length > 0 && (
              <button className="btn-primary" type="submit" disabled={saving}>
                {saving ? "Saving…" : "Save changes"}
              </button>
            )}
          </form>
        </div>
        <SiteFooter />
      </div>
    </div>
  );
}
