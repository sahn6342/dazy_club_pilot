import { useEffect, useMemo, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { useConfirm } from "../components/ConfirmDialog";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";

type Court = { id: string; venue_id: string; sport: string; name: string; capacity: number; active: boolean };
type Rule = {
  id: string; court_id: string; weekday: number;
  open_time: string; close_time: string; slot_minutes: number;
  price: number | null; discount_percent: number | null;
};
type Exc = { id: string; court_id: string | null; day: string; closed: boolean; open_time: string | null; close_time: string | null };

/** Local draft block for the weekly editor (not tied to a DB row — spans all 7 days). */
type DraftBlock = { key: string; open_time: string; close_time: string; slot_minutes: string; price: string; discount_percent: string };

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const ALL_DAYS = [0, 1, 2, 3, 4, 5, 6];
const inputStyle = { padding: "0.4rem 0.5rem", borderRadius: "6px", fontFamily: "inherit", width: "5.5rem" };

let _bk = 0;
const blockKey = () => `b${_bk++}`;

function ruleToDraft(r: Rule): DraftBlock {
  return {
    key: blockKey(),
    open_time: r.open_time, close_time: r.close_time,
    slot_minutes: String(r.slot_minutes),
    price: r.price == null ? "" : String(r.price),
    discount_percent: r.discount_percent == null ? "" : String(r.discount_percent),
  };
}

type DraftLike = { open_time: string; close_time: string; slot_minutes: string; price: string; discount_percent: string };
function draftToPayload(b: DraftLike): { open_time: string; close_time: string; slot_minutes: number; price: number | null; discount_percent: number | null } | string {
  const open = b.open_time.trim(), close = b.close_time.trim();
  if (open >= close) return `Block ${open}–${close}: open must be before close.`;
  const mins = Number(b.slot_minutes);
  if (!mins || mins < 15 || mins > 720 || !Number.isInteger(mins)) return "Slot minutes must be a whole number between 15 and 720.";
  const price = b.price === "" ? null : Number(b.price);
  if (price !== null && price < 0) return "Price cannot be negative.";
  const disc = b.discount_percent === "" ? null : Number(b.discount_percent);
  if (disc !== null && (disc < 0 || disc > 100)) return "Discount must be 0–100%.";
  return { open_time: open, close_time: close, slot_minutes: mins, price, discount_percent: disc };
}

/** Returns an overlap error message, or null if blocks are clean. */
function overlapError(blocks: Array<{ open_time: string; close_time: string }>): string | null {
  for (let i = 0; i < blocks.length; i++) {
    for (let j = i + 1; j < blocks.length; j++) {
      const a = blocks[i], b = blocks[j];
      if (a.open_time < b.close_time && b.open_time < a.close_time) {
        return `Blocks ${a.open_time}–${a.close_time} and ${b.open_time}–${b.close_time} overlap. Fix before saving.`;
      }
    }
  }
  return null;
}

/** True if every weekday has an identical set of blocks (so one weekly template is accurate). */
function allDaysIdentical(rules: Rule[]): boolean {
  const sig = (wd: number) =>
    rules.filter((r) => r.weekday === wd)
      .sort((a, b) => a.open_time.localeCompare(b.open_time))
      .map((r) => `${r.open_time}-${r.close_time}-${r.slot_minutes}-${r.price}-${r.discount_percent}`)
      .join("|");
  const first = sig(0);
  return ALL_DAYS.every((wd) => sig(wd) === first);
}

// ── Weekly editor ─────────────────────────────────────────────────────────────

function WeeklyEditor({ courtId, rules, onSaved }: { courtId: string; rules: Rule[]; onSaved: () => void }) {
  const toast = useToast();
  const [blocks, setBlocks] = useState<DraftBlock[]>([]);
  const [busy, setBusy] = useState(false);

  // Re-seed the template whenever the court's rules change. Use Monday as the
  // canonical week, falling back to whichever weekday has blocks.
  useEffect(() => {
    const seedDay = ALL_DAYS.find((wd) => rules.some((r) => r.weekday === wd));
    const seed = seedDay == null ? [] : rules.filter((r) => r.weekday === seedDay);
    setBlocks(seed.sort((a, b) => a.open_time.localeCompare(b.open_time)).map(ruleToDraft));
  }, [rules]);

  const identical = useMemo(() => allDaysIdentical(rules), [rules]);

  function update(key: string, field: keyof DraftBlock, value: string) {
    setBlocks((bs) => bs.map((b) => (b.key === key ? { ...b, [field]: value } : b)));
  }
  function addBlock() {
    setBlocks((bs) => [...bs, { key: blockKey(), open_time: "06:00", close_time: "12:00", slot_minutes: "60", price: "", discount_percent: "" }]);
  }
  function removeBlock(key: string) {
    setBlocks((bs) => bs.filter((b) => b.key !== key));
  }
  function makeContinuous() {
    const price = blocks[0]?.price ?? "";
    const disc = blocks[0]?.discount_percent ?? "";
    setBlocks([{ key: blockKey(), open_time: "06:00", close_time: "21:00", slot_minutes: "60", price, discount_percent: disc }]);
  }

  async function save() {
    const payloads = blocks.map(draftToPayload);
    const payloadErr = payloads.find((p) => typeof p === "string");
    if (payloadErr) { toast.error(payloadErr as string); return; }
    const overlapErr = overlapError(payloads as { open_time: string; close_time: string }[]);
    if (overlapErr) { toast.error(overlapErr); return; }
    setBusy(true);
    try {
      // Replace every weekday's rules with the current template.
      for (const wd of ALL_DAYS) {
        for (const r of rules.filter((r) => r.weekday === wd)) {
          await api.delete(`/admin/schedule/rules/${r.id}`);
        }
        for (const p of payloads) {
          await api.post("/admin/schedule/rules", { court_id: courtId, weekday: wd, ...(p as object) });
        }
      }
      onSaved();
      toast.success("Weekly schedule saved");
    } catch (err: any) {
      toast.error(err?.message ?? "Failed to save weekly schedule");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="schedule-card" data-testid="weekly-editor">
      <div className="enquiry-header">
        <h2 className="section-heading">Weekly hours</h2>
        <div className="action-row">
          <button className="btn-action secondary" onClick={makeContinuous} data-testid="weekly-continuous">Make continuous (06–21)</button>
        </div>
      </div>
      <p className="schedule-hint">
        One schedule applied to every day of the week. Saving overwrites all 7 days.
        {!identical && " (Days currently differ — saving makes them all match the hours below.)"}
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Open</th><th>Close</th><th>Slot min</th><th>Price (₹)</th><th>Discount %</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {blocks.length === 0 && (
              <tr><td colSpan={6}><span className="empty-msg">Closed all week — add hours below.</span></td></tr>
            )}
            {blocks.map((b) => (
              <tr key={b.key} className="weekly-block-row">
                <td><input className="cms-textarea" style={inputStyle} value={b.open_time} onChange={(e) => update(b.key, "open_time", e.target.value)} placeholder="HH:MM" /></td>
                <td><input className="cms-textarea" style={inputStyle} value={b.close_time} onChange={(e) => update(b.key, "close_time", e.target.value)} placeholder="HH:MM" /></td>
                <td><input className="cms-textarea" style={inputStyle} type="number" min="15" max="720" step="15" value={b.slot_minutes} onChange={(e) => update(b.key, "slot_minutes", e.target.value)} /></td>
                <td><input className="cms-textarea" style={inputStyle} type="number" min="0" value={b.price} onChange={(e) => update(b.key, "price", e.target.value)} placeholder="₹" /></td>
                <td><input className="cms-textarea" style={inputStyle} value={b.discount_percent} onChange={(e) => update(b.key, "discount_percent", e.target.value)} placeholder="%" /></td>
                <td><button className="btn-action delete" onClick={() => removeBlock(b.key)}>Remove</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="action-row" style={{ marginTop: "0.75rem" }}>
        <button className="btn-action secondary" onClick={addBlock} data-testid="weekly-add-block">Add block</button>
        <button className="btn-primary" onClick={save} disabled={busy} data-testid="weekly-save">{busy ? "Saving…" : "Save weekly schedule"}</button>
      </div>
    </div>
  );
}

// ── Per-day advanced rows ───────────────────────────────────────────────────────

function BlockRow({ rule, siblings, onSaved, onDeleted }: { rule: Rule; siblings: Rule[]; onSaved: () => void; onDeleted: () => void }) {
  const confirm = useConfirm();
  const toast = useToast();
  const [draft, setDraft] = useState({
    open_time: rule.open_time, close_time: rule.close_time,
    slot_minutes: String(rule.slot_minutes),
    price: rule.price == null ? "" : String(rule.price),
    discount_percent: rule.discount_percent == null ? "" : String(rule.discount_percent),
  });
  const [busy, setBusy] = useState(false);

  async function save() {
    const payload = draftToPayload(draft);
    if (typeof payload === "string") { toast.error(payload); return; }
    const others = siblings.filter((r) => r.id !== rule.id);
    const overlapErr = overlapError([payload, ...others]);
    if (overlapErr) { toast.error(overlapErr); return; }
    setBusy(true);
    try {
      await api.patch(`/admin/schedule/rules/${rule.id}`, payload);
      onSaved();
      toast.success("Block saved");
    } catch (err: any) {
      toast.error(err?.message ?? "Failed to save block");
    } finally {
      setBusy(false);
    }
  }

  async function del() {
    if (!await confirm({ message: "Delete this time block?", confirmLabel: "Delete", danger: true })) return;
    await api.delete(`/admin/schedule/rules/${rule.id}`);
    onDeleted();
    toast.success("Block deleted");
  }

  return (
    <tr className="block-row">
      <td><input className="cms-textarea" style={inputStyle} value={draft.open_time} onChange={(e) => setDraft((d) => ({ ...d, open_time: e.target.value }))} placeholder="HH:MM" /></td>
      <td><input className="cms-textarea" style={inputStyle} value={draft.close_time} onChange={(e) => setDraft((d) => ({ ...d, close_time: e.target.value }))} placeholder="HH:MM" /></td>
      <td><input className="cms-textarea" style={inputStyle} type="number" min="15" max="720" step="15" value={draft.slot_minutes} onChange={(e) => setDraft((d) => ({ ...d, slot_minutes: e.target.value }))} /></td>
      <td><input className="cms-textarea" style={inputStyle} type="number" min="0" value={draft.price} onChange={(e) => setDraft((d) => ({ ...d, price: e.target.value }))} placeholder="₹" /></td>
      <td><input className="cms-textarea" style={inputStyle} type="number" min="0" max="100" value={draft.discount_percent} onChange={(e) => setDraft((d) => ({ ...d, discount_percent: e.target.value }))} placeholder="%" /></td>
      <td>
        <div className="action-row">
          <button className="btn-action confirm" data-testid="save-block" onClick={save} disabled={busy}>Save</button>
          <button className="btn-action delete" onClick={del}>Delete</button>
        </div>
      </td>
    </tr>
  );
}

function AddBlock({ courtId, weekday, existing, onAdded }: { courtId: string; weekday: number; existing: Rule[]; onAdded: () => void }) {
  const toast = useToast();
  const [draft, setDraft] = useState({ open_time: "06:00", close_time: "12:00", slot_minutes: "60", price: "", discount_percent: "" });
  async function add() {
    const payload = draftToPayload(draft);
    if (typeof payload === "string") { toast.error(payload); return; }
    const overlapErr = overlapError([payload, ...existing]);
    if (overlapErr) { toast.error(overlapErr); return; }
    try {
      await api.post("/admin/schedule/rules", { court_id: courtId, weekday, ...payload });
      onAdded();
      toast.success("Block added");
    } catch (err: any) {
      toast.error(err?.message ?? "Failed to add block");
    }
  }
  return (
    <tr>
      <td><input className="cms-textarea" style={inputStyle} value={draft.open_time} onChange={(e) => setDraft((d) => ({ ...d, open_time: e.target.value }))} /></td>
      <td><input className="cms-textarea" style={inputStyle} value={draft.close_time} onChange={(e) => setDraft((d) => ({ ...d, close_time: e.target.value }))} /></td>
      <td><input className="cms-textarea" style={inputStyle} type="number" min="15" max="720" step="15" value={draft.slot_minutes} onChange={(e) => setDraft((d) => ({ ...d, slot_minutes: e.target.value }))} /></td>
      <td><input className="cms-textarea" style={inputStyle} type="number" min="0" value={draft.price} onChange={(e) => setDraft((d) => ({ ...d, price: e.target.value }))} placeholder="₹" /></td>
      <td><input className="cms-textarea" style={inputStyle} type="number" min="0" max="100" value={draft.discount_percent} onChange={(e) => setDraft((d) => ({ ...d, discount_percent: e.target.value }))} placeholder="%" /></td>
      <td><button className="btn-action confirm" data-testid={`add-block-${weekday}`} onClick={add}>Add block</button></td>
    </tr>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────────

export function Schedule() {
  const confirm = useConfirm();
  const toast = useToast();
  const [courts, setCourts] = useState<Court[]>([]);
  const [courtId, setCourtId] = useState("");
  const [rules, setRules] = useState<Rule[]>([]);
  const [exceptions, setExceptions] = useState<Exc[]>([]);
  const [excForm, setExcForm] = useState({ day: "", closed: true, open_time: "", close_time: "", allCourts: true });
  const [error, setError] = useState("");
  const [excError, setExcError] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  const courtName = (cid: string | null) =>
    cid == null ? "All courts" : (() => { const c = courts.find((x) => x.id === cid); return c ? `${c.sport} — ${c.name}` : cid; })();

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
    toast.success(`${WEEKDAYS[weekday]} set to one continuous block`);
  }

  async function closeDay(weekday: number) {
    if (!await confirm({ message: "Close this entire day? All bookings on this day will be blocked.", confirmLabel: "Close Day", danger: true })) return;
    for (const r of rules.filter((r) => r.weekday === weekday)) await api.delete(`/admin/schedule/rules/${r.id}`);
    loadSchedule();
    toast.success(`${WEEKDAYS[weekday]} closed`);
  }

  async function copyToAllDays(weekday: number) {
    const source = rules.filter((r) => r.weekday === weekday);
    if (!source.length) return;
    if (!await confirm({ message: "Copy this day's schedule to all days of the week?", confirmLabel: "Copy", danger: false })) return;
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
    toast.success(`${WEEKDAYS[weekday]} copied to all days`);
  }

  async function addException(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setExcError("");
    if (!excForm.day.trim()) {
      setExcError("Date is required.");
      return;
    }
    if (!excForm.closed) {
      if (!excForm.open_time || !excForm.close_time) { setError("Open and close times required for special hours."); return; }
      if (excForm.open_time >= excForm.close_time) { setError("Open time must be before close time."); return; }
    }
    try {
      await api.post("/admin/schedule/exceptions", {
        court_id: excForm.allCourts ? null : courtId, day: excForm.day, closed: excForm.closed,
        open_time: excForm.closed ? null : excForm.open_time,
        close_time: excForm.closed ? null : excForm.close_time,
      });
      setExcForm({ day: "", closed: true, open_time: "", close_time: "", allCourts: true });
      setExcError("");
      loadSchedule();
      toast.success("Exception added");
    } catch (err: any) {
      setError(err?.message ?? "Failed to add exception.");
      toast.error(err?.message ?? "Failed to add exception");
    }
  }

  async function deleteException(id: string) {
    if (!await confirm({ message: "Delete this schedule exception?", confirmLabel: "Delete", danger: true })) return;
    await api.delete(`/admin/schedule/exceptions/${id}`);
    loadSchedule();
    toast.success("Exception deleted");
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

          {/* Primary: single weekly schedule */}
          <WeeklyEditor courtId={courtId} rules={rules} onSaved={() => loadSchedule()} />

          {/* Advanced: per-day overrides */}
          <button
            className="advanced-toggle"
            data-testid="advanced-toggle"
            aria-expanded={showAdvanced}
            onClick={() => setShowAdvanced((s) => !s)}
          >
            {showAdvanced ? "▾" : "▸"} Customize individual days (advanced)
          </button>

          {showAdvanced && (
            <div data-testid="advanced-panel" style={{ marginTop: "1rem" }}>
              <p className="schedule-hint">
                Override a single weekday's hours. These take precedence over the weekly schedule above for that day only.
              </p>
              {WEEKDAYS.map((label, wd) => {
                const blocks = rules.filter((r) => r.weekday === wd).sort((a, b) => a.open_time.localeCompare(b.open_time));
                return (
                  <div key={wd} className="weekday-section" data-weekday={wd} style={{ marginBottom: "1.5rem" }}>
                    <div className="enquiry-header">
                      <h2 className="section-heading">{label}</h2>
                      <div className="action-row">
                        <button className="btn-action secondary" onClick={() => makeContinuous(wd)}>Make continuous</button>
                        <button className="btn-action secondary" onClick={() => copyToAllDays(wd)}>Copy to all days</button>
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
                            <BlockRow key={r.id} rule={r} siblings={blocks} onSaved={() => loadSchedule()} onDeleted={() => loadSchedule()} />
                          ))}
                          <AddBlock courtId={courtId} weekday={wd} existing={blocks} onAdded={() => loadSchedule()} />
                        </tbody>
                      </table>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <h2 className="section-heading" style={{ marginTop: "2rem" }}>Date exceptions (holidays / special hours)</h2>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Date</th><th>Court</th><th>Status</th><th>Hours</th><th>Actions</th></tr></thead>
              <tbody>
                {exceptions.length === 0 && <tr><td colSpan={5}><span className="empty-msg">No exceptions.</span></td></tr>}
                {exceptions.map((x) => (
                  <tr key={x.id} data-exc-court={x.court_id ?? "all"}>
                    <td>{x.day}</td>
                    <td>{courtName(x.court_id)}</td>
                    <td>{x.closed ? "Closed" : "Special hours"}</td>
                    <td>{x.closed ? "—" : `${x.open_time}–${x.close_time}`}</td>
                    <td><button className="btn-action delete" onClick={() => deleteException(x.id)}>Delete</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <form className="filter-bar" style={{ marginTop: "0.75rem", flexWrap: "wrap" }} onSubmit={addException}>
            <label className="muted" data-testid="exception-all-courts-label">
              <input type="checkbox" data-testid="exception-all-courts" checked={excForm.allCourts} onChange={(e) => setExcForm((f) => ({ ...f, allCourts: e.target.checked }))} /> Apply to all courts (holiday)
            </label>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.2rem" }}>
              <input
                className="cms-textarea"
                style={inputStyle}
                type="date"
                value={excForm.day}
                onChange={(e) => { setExcError(""); setExcForm((f) => ({ ...f, day: e.target.value })); }}
                data-testid="exception-date"
              />
              {excError && <span className="error-msg" style={{ fontSize: "0.8rem", marginTop: 0 }}>{excError}</span>}
            </div>
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
