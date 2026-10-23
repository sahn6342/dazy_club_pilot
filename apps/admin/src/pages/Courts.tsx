import { useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import { SiteFooter } from "../components/SiteFooter";

type Court = {
  id: string;
  venue_id: string;
  sport: string;
  name: string;
  capacity: number;
  active: boolean;
  createdAt: string;
  sports: string[]; // every sport bookable on this court; more than one = shared turf
};

const SPORTS = ["cricket", "football", "badminton", "pickleball"];
const SPORT_LABELS: Record<string, string> = {
  cricket: "Cricket",
  football: "Football",
  badminton: "Badminton",
  pickleball: "Pickleball",
};

const blankForm = { sport: "cricket", name: "", also: [] as string[] };

/** Checkboxes for the other sports a court is also used for (it always serves its own sport). */
function AlsoUsedFor({ primary, value, onChange }: { primary: string; value: string[]; onChange: (v: string[]) => void }) {
  const others = SPORTS.filter((s) => s !== primary);
  return (
    <fieldset data-testid="also-used-for" style={{ border: "none", padding: 0, margin: 0 }}>
      <legend className="muted" style={{ fontSize: "0.8rem", marginBottom: "0.25rem" }}>Also used for (shared turf)</legend>
      <span style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
        {others.map((s) => (
          <label key={s} style={{ display: "flex", gap: "0.35rem", alignItems: "center" }}>
            <input
              type="checkbox"
              data-testid={`also-${s}`}
              checked={value.includes(s)}
              onChange={(e) => onChange(e.target.checked ? [...value, s] : value.filter((x) => x !== s))}
            />
            {SPORT_LABELS[s]}
          </label>
        ))}
      </span>
      <span className="muted" style={{ fontSize: "0.75rem" }}>A slot booked under any ticked sport is taken for all of them.</span>
    </fieldset>
  );
}

export function Courts() {
  const toast = useToast();
  const [courts, setCourts] = useState<Court[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [form, setForm] = useState(blankForm);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  const [editId, setEditId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: "", also: [] as string[] });
  const [editError, setEditError] = useState("");
  const [saving, setSaving] = useState(false);

  function load() {
    setLoading(true);
    api.get<Court[]>("/admin/courts")
      .then((data) => { setCourts(data); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  }

  useEffect(() => { load(); }, []);

  async function createCourt(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) { setCreateError("Name is required."); return; }
    setCreating(true);
    setCreateError("");
    // Use venue_id from existing courts, fallback to "venue-dazy".
    const venueId = courts[0]?.venue_id ?? "venue-dazy";
    try {
      await api.post("/admin/courts", {
        venue_id: venueId,
        sport: form.sport,
        name: form.name.trim(),
        sports: [form.sport, ...form.also.filter((s) => s !== form.sport)],
      });
      toast.success("Court created");
      setForm(blankForm);
      load();
    } catch (err: any) {
      const msg = err?.message ?? "Failed to create";
      setCreateError(msg);
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  }

  function startEdit(c: Court) {
    setEditId(c.id);
    setEditForm({ name: c.name, also: (c.sports ?? []).filter((s) => s !== c.sport) });
    setEditError("");
  }

  async function saveEdit(court: Court) {
    if (!editForm.name.trim()) { setEditError("Name is required."); return; }
    setSaving(true);
    setEditError("");
    try {
      await api.patch(`/admin/courts/${court.id}`, {
        name: editForm.name.trim(),
        sports: [court.sport, ...editForm.also.filter((s) => s !== court.sport)],
      });
      toast.success("Court updated");
      setEditId(null);
      load();
    } catch (err: any) {
      const msg = err?.message ?? "Failed to update";
      setEditError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(c: Court) {
    try {
      if (c.active) {
        await api.delete(`/admin/courts/${c.id}`);
        toast.success(`${c.name} deactivated`);
      } else {
        await api.patch(`/admin/courts/${c.id}`, { active: true });
        toast.success(`${c.name} reactivated`);
      }
      load();
    } catch (err: any) {
      toast.error(err?.message ?? "Failed");
    }
  }

  const bySport = SPORTS.map((sport) => ({
    sport,
    courts: courts.filter((c) => c.sport === sport),
  }));

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Courts" />
        <div className="page-body">
          {error && <p className="error-msg">{error}</p>}

          {/* Create form */}
          <div style={{ marginBottom: "2rem", maxWidth: 560, background: "var(--surface-2, #1a1d24)", borderRadius: 12, padding: "1.25rem 1.5rem", border: "1px solid var(--border)" }}>
            <h3 style={{ marginBottom: "1rem", fontSize: "1rem" }}>Add court</h3>
            <form onSubmit={createCourt} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                <label style={{ flex: "1 1 140px" }}>
                  Sport
                  <select
                    value={form.sport}
                    onChange={(e) => setForm((f) => ({ ...f, sport: e.target.value }))}
                    className="cms-textarea"
                    style={{ marginTop: "0.25rem", width: "100%", padding: "0.45rem 0.65rem" }}
                  >
                    {SPORTS.map((s) => (
                      <option key={s} value={s}>{SPORT_LABELS[s]}</option>
                    ))}
                  </select>
                </label>
                <label style={{ flex: "2 1 200px" }}>
                  Name
                  <input
                    className="cms-textarea"
                    style={{ marginTop: "0.25rem", width: "100%", padding: "0.45rem 0.65rem" }}
                    value={form.name}
                    placeholder="e.g. Court 2"
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  />
                </label>
              </div>
              <AlsoUsedFor primary={form.sport} value={form.also.filter((s) => s !== form.sport)}
                onChange={(also) => setForm((f) => ({ ...f, also }))} />
              {createError && <p className="field-error">{createError}</p>}
              <div>
                <button className="btn-primary" type="submit" disabled={creating}>
                  {creating ? "Adding…" : "Add court"}
                </button>
              </div>
            </form>
          </div>

          {/* Courts grouped by sport */}
          {loading ? (
            <p className="muted">Loading…</p>
          ) : (
            bySport.map(({ sport, courts: sportCourts }) => (
              <div key={sport} style={{ marginBottom: "2rem" }}>
                <h3 style={{ fontSize: "0.95rem", marginBottom: "0.75rem", color: "var(--color-gold)" }}>
                  {SPORT_LABELS[sport]}
                </h3>
                {sportCourts.length === 0 ? (
                  (() => {
                    const hosts = courts.filter((c) => c.active && (c.sports ?? []).includes(sport));
                    return hosts.length ? (
                      <p className="muted" style={{ fontSize: "0.85rem" }} data-testid={`shares-${sport}`}>
                        Played on the shared {hosts.map((h) => `${SPORT_LABELS[h.sport]} — ${h.name}`).join(", ")}. Slots booked for either sport block the other.
                      </p>
                    ) : (
                      <p className="muted" style={{ fontSize: "0.85rem" }}>No courts — add one above.</p>
                    );
                  })()
                ) : (
                  <div className="table-wrap" style={{ maxWidth: 700 }}>
                  <table style={{ width: "100%" }}>
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Status</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sportCourts.map((c) => (
                        <tr key={c.id} data-testid={`court-row-${c.id}`} style={{ opacity: c.active ? 1 : 0.55 }}>
                          <td>
                            {editId === c.id ? (
                              <input
                                className="cms-textarea"
                                style={{ padding: "0.3rem 0.5rem", width: "100%", maxWidth: 200 }}
                                value={editForm.name}
                                onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                              />
                            ) : (
                              <>
                                {c.name}
                                {(c.sports ?? []).filter((s) => s !== c.sport).map((s) => (
                                  <span key={s} className="muted" data-testid={`shared-badge-${c.id}`}
                                    style={{ marginLeft: "0.5rem", fontSize: "0.75rem", border: "1px solid var(--border)", borderRadius: 999, padding: "0.05rem 0.5rem" }}>
                                    also {SPORT_LABELS[s] ?? s}
                                  </span>
                                ))}
                              </>
                            )}
                            {editId === c.id && (
                              <div style={{ marginTop: "0.5rem" }}>
                                <AlsoUsedFor primary={c.sport} value={editForm.also}
                                  onChange={(also) => setEditForm((f) => ({ ...f, also }))} />
                              </div>
                            )}
                          </td>
                          <td>
                            <span style={{ color: c.active ? "var(--color-success, #4ade80)" : "var(--color-muted, #888)" }}>
                              {c.active ? "Active" : "Inactive"}
                            </span>
                          </td>
                          <td>
                            {editId === c.id ? (
                              <span style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                                {editError && <span className="field-error" style={{ fontSize: "0.8rem" }}>{editError}</span>}
                                <button className="btn-action confirm" onClick={() => saveEdit(c)} disabled={saving}>
                                  {saving ? "…" : "Save"}
                                </button>
                                <button className="btn-action cancel" onClick={() => setEditId(null)}>Cancel</button>
                              </span>
                            ) : (
                              <span style={{ display: "flex", gap: "0.5rem" }}>
                                <button className="btn-action secondary" onClick={() => startEdit(c)}>Edit</button>
                                <button
                                  className={`btn-action ${c.active ? "delete" : "confirm"}`}
                                  onClick={() => toggleActive(c)}
                                >
                                  {c.active ? "Deactivate" : "Reactivate"}
                                </button>
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
        <SiteFooter />
      </div>
    </div>
  );
}
