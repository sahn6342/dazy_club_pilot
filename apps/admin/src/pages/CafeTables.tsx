import { useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { useConfirm } from "../components/ConfirmDialog";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";

type Table = { id: string; label: string; area: string | null; capacity: number; status: string; active: boolean; sortOrder: number };

const STATUS_COLOR: Record<string, string> = {
  free: "rgba(52,211,153,0.15)",
  occupied: "rgba(216,180,86,0.15)",
  reserved: "rgba(99,102,241,0.15)",
};
const STATUS_TEXT: Record<string, string> = { free: "#6ee7b7", occupied: "#d8b456", reserved: "#a5b4fc" };

const EMPTY_FORM = { label: "", area: "", capacity: "4", sortOrder: 0, status: "free" };

export function CafeTables() {
  const confirm = useConfirm();
  const toast = useToast();
  const [tables, setTables] = useState<Table[]>([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editTarget, setEditTarget] = useState<Table | null>(null);
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState("");

  const isEdit = !!editTarget;

  function load() {
    api.get<Table[]>("/admin/cafe/tables").then(setTables).catch(() => {});
  }
  useEffect(() => { load(); }, []);

  function startCreate() {
    setEditTarget(null);
    setForm(EMPTY_FORM);
    setServerError("");
  }

  function startEdit(t: Table) {
    setEditTarget(t);
    setForm({ label: t.label, area: t.area ?? "", capacity: String(t.capacity), sortOrder: t.sortOrder, status: t.status ?? "free" });
    setServerError("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.label.trim()) return;
    setSaving(true);
    setServerError("");
    const payload = { label: form.label.trim(), area: form.area || null, capacity: Number(form.capacity), sortOrder: form.sortOrder, status: form.status };
    try {
      if (isEdit) {
        await api.patch(`/admin/cafe/tables/${editTarget!.id}`, payload);
        toast.success("Table updated");
      } else {
        await api.post("/admin/cafe/tables", payload);
        toast.success("Table added");
      }
      startCreate();
      load();
    } catch (err: any) {
      setServerError(err?.message ?? "Failed");
      toast.error(err?.message ?? "Failed");
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(t: Table) {
    try {
      await api.patch(`/admin/cafe/tables/${t.id}`, { active: !t.active });
      load();
    } catch (err: any) { toast.error(err?.message ?? "Failed"); }
  }

  async function handleDelete(t: Table) {
    if (!await confirm({ message: "Delete this table?", confirmLabel: "Delete", danger: true })) return;
    try {
      await api.delete(`/admin/cafe/tables/${t.id}`);
      toast.success("Deleted");
      if (editTarget?.id === t.id) startCreate();
      load();
    } catch (err: any) { toast.error(err?.message ?? "Delete failed"); }
  }

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Café Tables" />
        <div className="page-body">
          <div className="users-split">

            <div className="users-list-col">
              {tables.length === 0 ? (
                <p className="empty-msg">No tables yet. Add one →</p>
              ) : (
                <div className="enquiry-list">
                  {tables.map((t) => (
                    <div key={t.id}
                      className={`enquiry-card${editTarget?.id === t.id ? " selected-card" : ""}`}
                      style={{ cursor: "pointer", opacity: t.active ? 1 : 0.55 }}
                      onClick={() => startEdit(t)}
                    >
                      <div className="enquiry-header">
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                          <strong>{t.label}</strong>
                          <span className="role-badge" style={{ background: STATUS_COLOR[t.status] ?? "rgba(100,100,100,0.15)", color: STATUS_TEXT[t.status] ?? "#888" }}>
                            {t.status}
                          </span>
                          {!t.active && <span className="role-badge" style={{ background: "rgba(100,100,100,0.15)", color: "#888" }}>inactive</span>}
                        </div>
                        <div style={{ display: "flex", gap: "0.4rem" }}>
                          <button className="btn-action secondary" onClick={(e) => { e.stopPropagation(); toggleActive(t); }}>
                            {t.active ? "Disable" : "Enable"}
                          </button>
                          <button className="btn-action cancel" onClick={(e) => { e.stopPropagation(); handleDelete(t); }}>Delete</button>
                        </div>
                      </div>
                      <div className="enquiry-detail">
                        <span>{t.area ?? "No area"}</span>
                        <span>Seats {t.capacity}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="users-form-col">
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
                <h2 className="section-heading" style={{ margin: 0 }}>
                  {isEdit ? `Edit — ${editTarget?.label}` : "Add table"}
                </h2>
                {isEdit && <button className="btn-action secondary" onClick={startCreate}>+ New</button>}
              </div>

              <form className="user-form" onSubmit={handleSubmit} noValidate>
                <div className="field-group">
                  <label className="cms-label">Label
                    <input
                      className="cms-textarea"
                      style={{ padding: "0.55rem 0.75rem", borderRadius: "8px", fontFamily: "inherit" }}
                      value={form.label}
                      onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))}
                      placeholder="e.g. T1, Counter, Outdoor 3"
                      required
                    />
                  </label>
                </div>

                <div className="field-group">
                  <label className="cms-label">Area
                    <input
                      className="cms-textarea"
                      style={{ padding: "0.55rem 0.75rem", borderRadius: "8px", fontFamily: "inherit" }}
                      value={form.area}
                      onChange={(e) => setForm((f) => ({ ...f, area: e.target.value }))}
                      placeholder="e.g. Indoor, Terrace, Counter"
                    />
                  </label>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div className="field-group">
                    <label className="cms-label">Capacity
                      <input
                        type="number" min="1" max="50"
                        className="cms-textarea"
                        style={{ padding: "0.55rem 0.75rem", borderRadius: "8px", fontFamily: "inherit" }}
                        value={form.capacity}
                        onChange={(e) => setForm((f) => ({ ...f, capacity: e.target.value }))}
                      />
                    </label>
                  </div>
                  <div className="field-group">
                    <label className="cms-label">Sort order
                      <input
                        type="number"
                        className="cms-textarea"
                        style={{ padding: "0.55rem 0.75rem", borderRadius: "8px", fontFamily: "inherit" }}
                        value={form.sortOrder}
                        onChange={(e) => setForm((f) => ({ ...f, sortOrder: Number(e.target.value) }))}
                      />
                    </label>
                  </div>
                </div>

                {isEdit && (
                  <div className="field-group">
                    <label className="cms-label">Status
                      <select
                        className="cms-textarea"
                        style={{ padding: "0.55rem 0.75rem", borderRadius: "8px", fontFamily: "inherit" }}
                        value={form.status}
                        onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}
                      >
                        <option value="free">Free</option>
                        <option value="occupied">Occupied</option>
                        <option value="reserved">Reserved</option>
                      </select>
                    </label>
                  </div>
                )}

                {serverError && <p className="error-msg">{serverError}</p>}
                <button className="btn-primary" type="submit" disabled={saving || !form.label.trim()}>
                  {saving ? "Saving…" : isEdit ? "Save changes" : "Add table"}
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
