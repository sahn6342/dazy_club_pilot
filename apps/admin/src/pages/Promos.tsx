import { useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { api } from "../lib/api";

type Promo = {
  id: string; code: string; kind: string; value: number; active: boolean;
  valid_from: string | null; valid_to: string | null;
  max_uses: number | null; used_count: number; sport_slug: string | null; createdAt: string;
};

const inputStyle = { padding: "0.55rem 0.75rem", borderRadius: "8px", fontFamily: "inherit" };
const emptyForm = { code: "", kind: "percent", value: "", valid_from: "", valid_to: "", max_uses: "", sport_slug: "", active: true };

export function Promos() {
  const [promos, setPromos] = useState<Promo[]>([]);
  const [form, setForm] = useState({ ...emptyForm });
  const [touched, setTouched] = useState(false);
  const [serverError, setServerError] = useState("");
  const [creating, setCreating] = useState(false);

  const codeErr = touched && !form.code.trim() ? "Code is required." : undefined;
  const valueErr = touched && !(Number(form.value) > 0) ? "Value must be greater than 0." : undefined;

  function load() {
    api.get<Promo[]>("/admin/promos").then(setPromos).catch((e) => setServerError(e.message));
  }
  useEffect(() => { load(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!form.code.trim() || !(Number(form.value) > 0)) return;
    setServerError("");
    setCreating(true);
    try {
      await api.post("/admin/promos", {
        code: form.code.trim().toUpperCase(),
        kind: form.kind,
        value: Number(form.value),
        active: form.active,
        valid_from: form.valid_from || null,
        valid_to: form.valid_to || null,
        max_uses: form.max_uses === "" ? null : Number(form.max_uses),
        sport_slug: form.sport_slug || null,
      });
      setForm({ ...emptyForm });
      setTouched(false);
      load();
    } catch (err: any) {
      setServerError(err?.message ?? "Failed to create promo.");
    } finally {
      setCreating(false);
    }
  }

  async function toggleActive(p: Promo) {
    await api.patch(`/admin/promos/${p.id}`, { active: !p.active });
    load();
  }

  async function remove(p: Promo) {
    if (!window.confirm(`Delete promo "${p.code}"?`)) return;
    await api.delete(`/admin/promos/${p.id}`);
    load();
  }

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Promos" />
        <div className="page-body">
          <div className="users-split">
            <div className="users-list-col">
              <h2 className="section-heading">Promo codes</h2>
              {promos.length === 0 ? (
                <p className="empty-msg">No promo codes yet.</p>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr><th>Code</th><th>Discount</th><th>Validity</th><th>Uses</th><th>Sport</th><th>Active</th><th>Actions</th></tr>
                    </thead>
                    <tbody>
                      {promos.map((p) => (
                        <tr key={p.id} className="promo-row" data-code={p.code}>
                          <td><code>{p.code}</code></td>
                          <td>{p.kind === "percent" ? `${p.value}%` : `₹${p.value}`}</td>
                          <td>{p.valid_from || p.valid_to ? `${p.valid_from ?? "…"} → ${p.valid_to ?? "…"}` : "Always"}</td>
                          <td>{p.used_count}{p.max_uses != null ? ` / ${p.max_uses}` : ""}</td>
                          <td>{p.sport_slug ?? "All"}</td>
                          <td>
                            <button className={`btn-action ${p.active ? "confirm" : "cancel"}`} onClick={() => toggleActive(p)}>
                              {p.active ? "Active" : "Inactive"}
                            </button>
                          </td>
                          <td><button className="btn-action delete" onClick={() => remove(p)}>Remove</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="users-form-col">
              <h2 className="section-heading">Add promo code</h2>
              <form className="user-form" onSubmit={handleCreate} noValidate>
                <div className="field-group">
                  <label className="cms-label">Code
                    <input className={`cms-textarea${codeErr ? " input-error" : ""}`} style={inputStyle}
                      data-testid="promo-code" value={form.code}
                      onChange={(e) => setForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}
                      placeholder="WELCOME10" />
                  </label>
                  {codeErr && <p className="field-error">{codeErr}</p>}
                </div>

                <div className="field-group">
                  <label className="cms-label">Type
                    <select className="cms-textarea" style={inputStyle} data-testid="promo-kind"
                      value={form.kind} onChange={(e) => setForm((f) => ({ ...f, kind: e.target.value }))}>
                      <option value="percent">Percent (%)</option>
                      <option value="flat">Flat (₹)</option>
                    </select>
                  </label>
                </div>

                <div className="field-group">
                  <label className="cms-label">Value
                    <input className={`cms-textarea${valueErr ? " input-error" : ""}`} style={inputStyle}
                      data-testid="promo-value" type="number" value={form.value}
                      onChange={(e) => setForm((f) => ({ ...f, value: e.target.value }))}
                      placeholder={form.kind === "percent" ? "10" : "100"} />
                  </label>
                  {valueErr && <p className="field-error">{valueErr}</p>}
                </div>

                <div className="field-group">
                  <label className="cms-label">Sport
                    <select className="cms-textarea" style={inputStyle}
                      value={form.sport_slug} onChange={(e) => setForm((f) => ({ ...f, sport_slug: e.target.value }))}>
                      <option value="">All sports</option>
                      <option value="cricket">Cricket</option>
                      <option value="badminton">Badminton</option>
                      <option value="pickleball">Pickleball</option>
                    </select>
                  </label>
                </div>

                <div className="field-group">
                  <label className="cms-label">Valid from
                    <input className="cms-textarea" style={inputStyle} type="date" value={form.valid_from}
                      onChange={(e) => setForm((f) => ({ ...f, valid_from: e.target.value }))} />
                  </label>
                </div>
                <div className="field-group">
                  <label className="cms-label">Valid to
                    <input className="cms-textarea" style={inputStyle} type="date" value={form.valid_to}
                      onChange={(e) => setForm((f) => ({ ...f, valid_to: e.target.value }))} />
                  </label>
                </div>
                <div className="field-group">
                  <label className="cms-label">Max uses (optional)
                    <input className="cms-textarea" style={inputStyle} type="number" value={form.max_uses}
                      onChange={(e) => setForm((f) => ({ ...f, max_uses: e.target.value }))} placeholder="unlimited" />
                  </label>
                </div>
                <label className="cms-label">
                  <input type="checkbox" checked={form.active} onChange={(e) => setForm((f) => ({ ...f, active: e.target.checked }))} /> Active
                </label>

                {serverError && <p className="error-msg">{serverError}</p>}
                <button className="btn-primary" type="submit" data-testid="promo-submit" disabled={creating}>
                  {creating ? "Creating…" : "Add promo"}
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
