import { useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { api } from "../lib/api";

type Court = { id: string; venue_id: string; sport: string; name: string; capacity: number; active: boolean };
type Rule = {
  id: string; court_id: string; weekday: number;
  open_time: string; close_time: string; slot_minutes: number;
  price: number | null; discount_percent: number | null;
};
type Exc = { id: string; court_id: string; day: string; closed: boolean; open_time: string | null; close_time: string | null };

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const inputStyle = { padding: "0.4rem 0.5rem", borderRadius: "6px", fontFamily: "inherit", width: "5.5rem" };

function BlockRow({ rule, onSaved, onDeleted }: { rule: Rule; onSaved: () => void; onDeleted: () => void }) {
  const [draft, setDraft] = useState({
    open_time: rule.open_time, close_time: rule.close_time,
    slot_minutes: String(rule.slot_minutes),
    price: rule.price == null ? "" : String(rule.price),
    discount_percent: rule.discount_percent == null ? "" : String(rule.discount_percent),
  });
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      await api.patch(`/admin/schedule/rules/${rule.id}`, {
        open_time: draft.open_time,
        close_time: draft.close_time,
        slot_minutes: Number(draft.slot_minutes),
        price: draft.price === "" ? null : Number(draft.price),
        discount_percent: draft.discount_percent === "" ? null : Number(draft.discount_percent),
      });
      onSaved();
    } finally {
      setBusy(false);
    }
  }

  async function del() {
    if (!window.confirm("Delete this block?")) return;
    await api.delete(`/admin/schedule/rules/${rule.id}`);
    onDeleted();
  }

  return (
    <tr className="block-row">
      <td><input className="cms-textarea" style={inputStyle} value={draft.open_time} onChange={(e) => setDraft((d) => ({ ...d, open_time: e.target.value }))} placeholder="HH:MM" /></td>
      <td><input className="cms-textarea" style={inputStyle} value={draft.close_time} onChange={(e) => setDraft((d) => ({ ...d, close_time: e.target.value }))} placeholder="HH:MM" /></td>
      <td><input className="cms-textarea" style={inputStyle} value={draft.slot_minutes} onChange={(e) => setDraft((d) => ({ ...d, slot_minutes: e.target.value }))} /></td>
      <td><input className="cms-textarea" style={inputStyle} value={draft.price} onChange={(e) => setDraft((d) => ({ ...d, price: e.target.value }))} placeholder="₹" /></td>
      <td><input className="cms-textarea" style={inputStyle} value={draft.discount_percent} onChange={(e) => setDraft((d) => ({ ...d, discount_percent: e.target.value }))} placeholder="%" /></td>
      <td>
        <div className="action-row">
          <button className="btn-action confirm" data-testid="save-block" onClick={save} disabled={busy}>Save</button>
          <button className="btn-action delete" onClick={del}>Delete</button>
        </div>
      </td>
    </tr>
  );
}

function AddBlock({ courtId, weekday, onAdded }: { courtId: string; weekday: number; onAdded: () => void }) {
  const [draft, setDraft] = useState({ open_time: "06:00", close_time: "12:00", slot_minutes: "60", price: "", discount_percent: "" });
  async function add() {
    await api.post("/admin/schedule/rules", {
      court_id: courtId, weekday,
      open_time: draft.open_time, close_time: draft.close_time,
      slot_minutes: Number(draft.slot_minutes),
      price: draft.price === "" ? null : Number(draft.price),
      discount_percent: draft.discount_percent === "" ? null : Number(draft.discount_percent),
    });
    onAdded();
  }
  return (
    <tr>
      <td><input className="cms-textarea" style={inputStyle} value={draft.open_time} onChange={(e) => setDraft((d) => ({ ...d, open_time: e.target.value }))} /></td>
      <td><input className="cms-textarea" style={inputStyle} value={draft.close_time} onChange={(e) => setDraft((d) => ({ ...d, close_time: e.target.value }))} /></td>
      <td><input className="cms-textarea" style={inputStyle} value={draft.slot_minutes} onChange={(e) => setDraft((d) => ({ ...d, slot_minutes: e.target.value }))} /></td>
      <td><input className="cms-textarea" style={inputStyle} value={draft.price} onChange={(e) => setDraft((d) => ({ ...d, price: e.target.value }))} placeholder="₹" /></td>
      <td><input className="cms-textarea" style={inputStyle} value={draft.discount_percent} onChange={(e) => setDraft((d) => ({ ...d, discount_percent: e.target.value }))} placeholder="%" /></td>
      <td><button className="btn-action confirm" data-testid={`add-block-${weekday}`} onClick={add}>Add block</button></td>
    </tr>
  );
}

export function Schedule() {
  const [courts, setCourts] = useState<Court[]>([]);
  const [courtId, setCourtId] = useState("");
  const [rules, setRules] = useState<Rule[]>([]);
  const [exceptions, setExceptions] = useState<Exc[]>([]);
  const [excForm, setExcForm] = useState({ day: "", closed: true, open_time: "", close_time: "" });
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<Court[]>("/admin/courts")
      .then((cs) => { setCourts(cs); if (cs[0]) setCourtId(cs[0].id); })
      .catch((e) => setError(e.message));
  }, []);

  function loadSchedule(cid = courtId) {
    if (!cid) return;
    api.get<Rule[]>(`/admin/schedule/rules?court_id=${cid}`).then(setRules).catch((e) => setError(e.message));
    api.get<Exc[]>(`/admin/schedule/exceptions?court_id=${cid}`).then(setExceptions).catch(() => {});
  }

  useEffect(() => { loadSchedule(); }, [courtId]);

  async function makeContinuous(weekday: number) {
    const existing = rules.filter((r) => r.weekday === weekday);
    const price = existing[0]?.price ?? null;
    for (const r of existing) await api.delete(`/admin/schedule/rules/${r.id}`);
    await api.post("/admin/schedule/rules", { court_id: courtId, weekday, open_time: "06:00", close_time: "21:00", slot_minutes: 60, price, discount_percent: existing[0]?.discount_percent ?? null });
    loadSchedule();
  }

  async function closeDay(weekday: number) {
    if (!window.confirm(`Close ${WEEKDAYS[weekday]}? All blocks for that day are removed.`)) return;
    for (const r of rules.filter((r) => r.weekday === weekday)) await api.delete(`/admin/schedule/rules/${r.id}`);
    loadSchedule();
  }

  async function copyToAllDays(weekday: number) {
    const source = rules.filter((r) => r.weekday === weekday);
    if (!source.length) return;
    if (!window.confirm(`Copy ${WEEKDAYS[weekday]} hours + prices to all 7 days?`)) return;
    for (let wd = 0; wd < 7; wd++) {
      if (wd === weekday) continue;
      for (const r of rules.filter((r) => r.weekday === wd)) await api.delete(`/admin/schedule/rules/${r.id}`);
      for (const b of source) {
        await api.post("/admin/schedule/rules", {
          court_id: courtId, weekday: wd, open_time: b.open_time, close_time: b.close_time,
          slot_minutes: b.slot_minutes, price: b.price, discount_percent: b.discount_percent,
        });
      }
    }
    loadSchedule();
  }

  async function addException(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/admin/schedule/exceptions", {
        court_id: courtId, day: excForm.day, closed: excForm.closed,
        open_time: excForm.closed ? null : (excForm.open_time || null),
        close_time: excForm.closed ? null : (excForm.close_time || null),
      });
      setExcForm({ day: "", closed: true, open_time: "", close_time: "" });
      loadSchedule();
    } catch (err: any) {
      setError(err?.message ?? "Failed to add exception.");
    }
  }

  async function deleteException(id: string) {
    await api.delete(`/admin/schedule/exceptions/${id}`);
    loadSchedule();
  }

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Schedule" />
        <div className="page-body">
          <div className="filter-bar">
            <label className="muted">Court&nbsp;
              <select data-testid="court-select" value={courtId} onChange={(e) => setCourtId(e.target.value)}>
                {courts.map((c) => (
                  <option key={c.id} value={c.id}>{c.sport} — {c.name}</option>
                ))}
              </select>
            </label>
          </div>
          {error && <p className="error-msg">{error}</p>}

          {WEEKDAYS.map((label, wd) => {
            const blocks = rules.filter((r) => r.weekday === wd).sort((a, b) => a.open_time.localeCompare(b.open_time));
            return (
              <div key={wd} className="weekday-section" data-weekday={wd} style={{ marginBottom: "1.5rem" }}>
                <div className="enquiry-header">
                  <h2 className="section-heading">{label}</h2>
                  <div className="action-row">
                    <button className="btn-action" onClick={() => makeContinuous(wd)}>Make continuous</button>
                    <button className="btn-action" onClick={() => copyToAllDays(wd)}>Copy to all days</button>
                    <button className="btn-action cancel" onClick={() => closeDay(wd)}>Close day</button>
                  </div>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr><th>Open</th><th>Close</th><th>Slot min</th><th>Price (₹)</th><th>Discount %</th><th>Actions</th></tr>
                    </thead>
                    <tbody>
                      {blocks.length === 0 && (
                        <tr><td colSpan={6}><span className="empty-msg">Closed — add hours below</span></td></tr>
                      )}
                      {blocks.map((r) => (
                        <BlockRow key={r.id} rule={r} onSaved={() => loadSchedule()} onDeleted={() => loadSchedule()} />
                      ))}
                      <AddBlock courtId={courtId} weekday={wd} onAdded={() => loadSchedule()} />
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })}

          <h2 className="section-heading" style={{ marginTop: "2rem" }}>Date exceptions (holidays / special hours)</h2>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Date</th><th>Status</th><th>Hours</th><th>Actions</th></tr></thead>
              <tbody>
                {exceptions.length === 0 && <tr><td colSpan={4}><span className="empty-msg">No exceptions.</span></td></tr>}
                {exceptions.map((x) => (
                  <tr key={x.id}>
                    <td>{x.day}</td>
                    <td>{x.closed ? "Closed" : "Special hours"}</td>
                    <td>{x.closed ? "—" : `${x.open_time}–${x.close_time}`}</td>
                    <td><button className="btn-action delete" onClick={() => deleteException(x.id)}>Delete</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <form className="filter-bar" style={{ marginTop: "0.75rem", flexWrap: "wrap" }} onSubmit={addException}>
            <input className="cms-textarea" style={inputStyle} type="date" value={excForm.day} onChange={(e) => setExcForm((f) => ({ ...f, day: e.target.value }))} required />
            <label className="muted">
              <input type="checkbox" checked={excForm.closed} onChange={(e) => setExcForm((f) => ({ ...f, closed: e.target.checked }))} /> Closed
            </label>
            {!excForm.closed && (
              <>
                <input className="cms-textarea" style={inputStyle} placeholder="Open HH:MM" value={excForm.open_time} onChange={(e) => setExcForm((f) => ({ ...f, open_time: e.target.value }))} />
                <input className="cms-textarea" style={inputStyle} placeholder="Close HH:MM" value={excForm.close_time} onChange={(e) => setExcForm((f) => ({ ...f, close_time: e.target.value }))} />
              </>
            )}
            <button className="btn-primary" type="submit" data-testid="exception-add">Add exception</button>
          </form>
        </div>
      </div>
    </div>
  );
}
