import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { SiteFooter } from "../components/SiteFooter";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";

type Slot = {
  id: string; courtId: string; courtName: string; sportSlug: string; date: string;
  startTime: string; endTime: string; available: boolean; maxPlayers: number;
  price: number | null; discountPercent: number | null; finalPrice: number | null;
};

type Created = {
  bookingRef: string; name: string; sport: string; date: string; startTime: string; endTime: string;
  price: number | null; paymentMode: "cash" | "upi";
};

const SPORTS: Record<string, string> = { cricket: "Cricket", football: "Football", badminton: "Badminton", pickleball: "Pickleball" };
const PHONE_RE = /^\d{10}$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const inr = (n: number) => `₹${n.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

function nextDays() {
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() + i);
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    return { iso, label: d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" }) };
  });
}

function duration(slots: Slot[]) {
  const toMin = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3));
  let mins = toMin(slots[slots.length - 1].endTime) - toMin(slots[0].startTime);
  if (mins <= 0) mins += 1440;
  const h = Math.floor(mins / 60), m = mins % 60;
  return [h ? `${h} hr` : "", m ? `${m} min` : ""].filter(Boolean).join(" ");
}

/** Book a slot at the counter: staff pick the slots, take cash or UPI, and the booking is confirmed at once (no Razorpay). */
export function WalkInBooking() {
  const toast = useToast();
  const days = useMemo(nextDays, []);
  const [sport, setSport] = useState("cricket");
  const [date, setDate] = useState(days[0].iso);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [loading, setLoading] = useState(false);
  const [slotsError, setSlotsError] = useState("");
  const [courtId, setCourtId] = useState("all");
  const [selected, setSelected] = useState<Slot[]>([]);
  const [name, setName] = useState("");
  const [contact, setContact] = useState("");
  const [players, setPlayers] = useState("1");
  const [promo, setPromo] = useState("");
  const [mode, setMode] = useState<"cash" | "upi">("cash");
  const [reference, setReference] = useState("");
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState<Created | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const request = useRef(0);

  useEffect(() => {
    const id = ++request.current;
    setLoading(true);
    setSelected([]);
    api.get<Slot[]>(`/admin/slots?sport=${sport}&date=${date}`)
      .then((data) => { if (id === request.current) { setSlots(data); setSlotsError(""); } })
      .catch((e) => { if (id === request.current) { setSlots([]); setSlotsError(e?.message ?? "Could not load slots"); } })
      .finally(() => { if (id === request.current) setLoading(false); });
  }, [sport, date, reloadKey]);

  const courts = useMemo(() => {
    const seen = new Map<string, string>();
    slots.forEach((s) => seen.set(s.courtId, s.courtName));
    return [...seen].map(([id, label]) => ({ id, label }));
  }, [slots]);
  const shown = courtId === "all" ? slots : slots.filter((s) => s.courtId === courtId);

  function pick(slot: Slot) {
    if (!slot.available) return;
    const last = selected[selected.length - 1];
    if (!last) return setSelected([slot]);
    if (slot.id === last.id) return setSelected(selected.slice(0, -1)); // tap the last one again to trim it
    if (slot.startTime === last.endTime && slot.courtId === last.courtId && selected.length < 8) return setSelected([...selected, slot]);
    setSelected([slot]);
  }

  const total = selected.length && selected.every((s) => s.finalPrice != null)
    ? selected.reduce((sum, s) => sum + (s.finalPrice ?? 0), 0) : null;
  const playersN = Number(players);
  const nameErr = name.trim() ? "" : "Enter the customer's name.";
  const contactErr = PHONE_RE.test(contact.trim()) || EMAIL_RE.test(contact.trim()) ? "" : "Enter a 10-digit mobile number or an email address.";
  const playersErr = Number.isInteger(playersN) && playersN >= 1 && playersN <= 25 ? "" : "Players must be 1 to 25.";
  const invalid = !selected.length || !!(nameErr || contactErr || playersErr);

  async function submit() {
    setTouched(true);
    if (invalid || busy) return;
    setBusy(true);
    setError("");
    try {
      const r = await api.post<Created>("/admin/bookings/walkin", {
        name: name.trim(), contact: contact.trim(), slotIds: selected.map((s) => s.id), sportSlug: sport, date,
        players: playersN, paymentMode: mode, reference: mode === "upi" && reference.trim() ? reference.trim() : undefined,
        promoCode: promo.trim() || undefined,
      });
      setCreated(r);
      toast.success(`Booking ${r.bookingRef} confirmed`);
    } catch (e: any) {
      setError(e?.message ?? "The booking could not be saved.");
      setReloadKey((k) => k + 1); // a clash means the grid is stale
    } finally {
      setBusy(false);
    }
  }

  function another() {
    setCreated(null); setSelected([]); setName(""); setContact(""); setPlayers("1"); setPromo(""); setReference("");
    setMode("cash"); setTouched(false); setError(""); setReloadKey((k) => k + 1);
  }

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Walk-in booking" />
        <div className="page-body walkin-page">
          {created ? (
            <div className="walkin-done" data-testid="walkin-done">
              <h2>Booking confirmed</h2>
              <p>
                <code data-testid="walkin-ref">{created.bookingRef}</code> · {created.name} · {SPORTS[created.sport]} ·{" "}
                {created.date} {created.startTime}–{created.endTime}
              </p>
              <p>
                {created.price != null ? <strong>{inr(created.price)}</strong> : "Free"} received by{" "}
                <strong>{created.paymentMode === "upi" ? "UPI" : "cash"}</strong>.
              </p>
              <div className="action-row">
                <button className="btn-primary small" data-testid="walkin-another" onClick={another}>Book another</button>
                <Link className="btn-action secondary" to="/bookings">View bookings</Link>
              </div>
            </div>
          ) : (
            <>
              <p className="muted">Paid at the counter in cash or UPI. The booking is confirmed straight away; no online payment is used.</p>
              <div className="filter-bar" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
                <select data-testid="walkin-sport" value={sport} onChange={(e) => { setSport(e.target.value); setCourtId("all"); }}>
                  {Object.entries(SPORTS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
                <select data-testid="walkin-date" value={date} onChange={(e) => setDate(e.target.value)}>
                  {days.map((d, i) => <option key={d.iso} value={d.iso}>{i === 0 ? `Today · ${d.label}` : d.label}</option>)}
                </select>
              </div>

              {courts.length > 1 && (
                <div className="court-pills" role="group" aria-label="Select court">
                  {[{ id: "all", label: "All courts" }, ...courts].map((c) => (
                    <button key={c.id} className={`court-pill${courtId === c.id ? " active" : ""}`}
                      onClick={() => { setCourtId(c.id); setSelected([]); }}>{c.label}</button>
                  ))}
                </div>
              )}

              {loading ? <p className="muted">Loading slots…</p>
                : slotsError ? <p className="field-error">{slotsError}</p>
                : shown.length === 0 ? <p className="empty-msg">No slots left for this selection.</p>
                : (
                  <div className="slot-grid" data-testid="walkin-slots">
                    {shown.map((s) => {
                      const on = selected.some((x) => x.id === s.id);
                      return (
                        <button key={s.id} disabled={!s.available} data-testid={`walkin-slot-${s.id}`}
                          className={["slot-chip", !s.available ? "unavailable" : "", on ? "selected" : ""].filter(Boolean).join(" ")}
                          onClick={() => pick(s)} title={s.available ? `${s.startTime}–${s.endTime}` : "Already booked"}>
                          {s.startTime}
                          {courtId === "all" && courts.length > 1 && <span className="slot-court-label">{s.courtName}</span>}
                          <span className="slot-price">{s.finalPrice != null ? inr(s.finalPrice) : "Free"}</span>
                          {!s.available && <span className="slot-booked-tag">Booked</span>}
                        </button>
                      );
                    })}
                  </div>
                )}

              {selected.length > 0 && (
                <div className="walkin-form" data-testid="walkin-form">
                  <p className="walkin-summary" data-testid="walkin-summary">
                    {selected[0].courtName} · {selected[0].startTime}–{selected[selected.length - 1].endTime} ({duration(selected)}) ·{" "}
                    <strong data-testid="walkin-total">{total != null ? inr(total) : "Free"}</strong>
                    <small className="muted"> {selected.length > 1 ? "Tap the last slot to shorten, or an adjacent one to extend." : "Tap the next slot to book more hours."}</small>
                  </p>

                  <label className="field-group">Customer name
                    <input data-testid="walkin-name" className="cms-textarea" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
                    {touched && nameErr && <span className="field-error">{nameErr}</span>}
                  </label>
                  <label className="field-group">Phone (or email)
                    <input data-testid="walkin-contact" className="cms-textarea" inputMode="tel" value={contact} onChange={(e) => setContact(e.target.value)} />
                    {touched && contactErr && <span className="field-error">{contactErr}</span>}
                  </label>
                  <label className="field-group">Players
                    <input data-testid="walkin-players" className="cms-textarea" type="number" min={1} max={25} value={players} onChange={(e) => setPlayers(e.target.value)} />
                    {touched && playersErr && <span className="field-error">{playersErr}</span>}
                  </label>
                  <label className="field-group">Promo code (optional)
                    <input data-testid="walkin-promo" className="cms-textarea" maxLength={40} value={promo} onChange={(e) => setPromo(e.target.value)} />
                  </label>

                  <fieldset className="walkin-mode">
                    <legend>Payment received by</legend>
                    {(["cash", "upi"] as const).map((m) => (
                      <label key={m}><input type="radio" name="walkin-mode" data-testid={`walkin-mode-${m}`} checked={mode === m} onChange={() => setMode(m)} /> {m === "cash" ? "Cash" : "UPI"}</label>
                    ))}
                  </fieldset>
                  {mode === "upi" && (
                    <label className="field-group">UPI reference (optional)
                      <input data-testid="walkin-reference" className="cms-textarea" maxLength={100} value={reference} onChange={(e) => setReference(e.target.value)} />
                    </label>
                  )}

                  {error && <p className="field-error" data-testid="walkin-error">{error}</p>}
                  <button className="btn-primary" data-testid="walkin-submit" disabled={busy} onClick={submit}>
                    {busy ? "Saving…" : `Confirm booking${total != null ? ` · ${inr(total)} ${mode === "upi" ? "UPI" : "cash"}` : ""}`}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
        <SiteFooter />
      </div>
    </div>
  );
}
