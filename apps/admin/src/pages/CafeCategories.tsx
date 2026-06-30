import { useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { useConfirm } from "../components/ConfirmDialog";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";

type Category = { id: string; name: string; kind: string; vegType: string | null; sortOrder: number; active: boolean; createdAt: string };

const KIND_OPTS = ["food", "beverage", "packaged", "combo"];
const VEG_OPTS = [{ val: "", label: "— none —" }, { val: "veg", label: "Veg" }, { val: "nonveg", label: "Non-veg" }, { val: "egg", label: "Egg" }, { val: "na", label: "N/A" }];

const EMPTY = { name: "", kind: "food", vegType: "", sortOrder: 0 };

export function CafeCategories() {
  const confirm = useConfirm();
  const toast = useToast();
  const [cats, setCats] = useState<Category[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [editTarget, setEditTarget] = useState<Category | null>(null);
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState("");

  const isEdit = !!editTarget;

  function load() {
    api.get<Category[]>("/admin/cafe/categories").then(setCats).catch(() => {});
  }
  useEffect(() => { load(); }, []);

  function startCreate() {
    setEditTarget(null);
    setForm(EMPTY);
    setServerError("");
  }

  function startEdit(c: Category) {
    setEditTarget(c);
    setForm({ name: c.name, kind: c.kind, vegType: c.vegType ?? "", sortOrder: c.sortOrder });
    setServerError("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    setServerError("");
    const payload = { name: form.name.trim(), kind: form.kind, vegType: form.vegType || null, sortOrder: form.sortOrder };
    try {
      if (isEdit) {
        await api.patch(`/admin/cafe/categories/${editTarget!.id}`, payload);
        toast.success("Category updated");
      } else {
        await api.post("/admin/cafe/categories", payload);
        toast.success("Category added");
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

  async function toggleActive(c: Category) {
    try {
      await api.patch(`/admin/cafe/categories/${c.id}`, { active: !c.active });
      load();
    } catch (err: any) { toast.error(err?.message ?? "Failed"); }
  }

  async function handleDelete(c: Category) {
    if (!await confirm({ message: "Delete this category?", confirmLabel: "Delete", danger: true })) return;
    try {
      await api.delete(`/admin/cafe/categories/${c.id}`);
      toast.success("Deleted");
      if (editTarget?.id === c.id) startCreate();
      load();
    } catch (err: any) { toast.error(err?.message ?? "Delete failed"); }
  }

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Menu Categories" />
        <div className="page-body">
          <div className="users-split">

            <div className="users-list-col">
              {cats.length === 0 ? (
                <p className="empty-msg">No categories yet. Add one →</p>
              ) : (
                <div className="enquiry-list">
                  {cats.map((c) => (
                    <div key={c.id}
                      className={`enquiry-card${editTarget?.id === c.id ? " selected-card" : ""}`}
                      style={{ cursor: "pointer", opacity: c.active ? 1 : 0.55 }}
                      onClick={() => startEdit(c)}
                    >
                      <div className="enquiry-header">
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                          <strong>{c.name}</strong>
                          <span className="cafe-kind-badge">{c.kind}</span>
                          {c.vegType && <span className="cafe-veg-badge">{c.vegType}</span>}
                          {!c.active && <span className="role-badge" style={{ background: "rgba(100,100,100,0.15)", color: "#888" }}>inactive</span>}
                        </div>
                        <div style={{ display: "flex", gap: "0.4rem" }}>
                          <button className="btn-action secondary" onClick={(e) => { e.stopPropagation(); toggleActive(c); }}>
                            {c.active ? "Disable" : "Enable"}
                          </button>
                          <button className="btn-action cancel" onClick={(e) => { e.stopPropagation(); handleDelete(c); }}>Delete</button>
                        </div>
                      </div>
                      <div className="enquiry-detail">
                        <span>Sort: {c.sortOrder}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="users-form-col">
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
                <h2 className="section-heading" style={{ margin: 0 }}>
                  {isEdit ? `Edit — ${editTarget?.name}` : "Add category"}
                </h2>
                {isEdit && <button className="btn-action secondary" onClick={startCreate}>+ New</button>}
              </div>

              <form className="user-form" onSubmit={handleSubmit} noValidate>
                <div className="field-group">
                  <label className="cms-label">Name
                    <input
                      className="cms-textarea"
                      style={{ padding: "0.55rem 0.75rem", borderRadius: "8px", fontFamily: "inherit" }}
                      value={form.name}
                      onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                      placeholder="e.g. Starters, Drinks, Desserts"
                      required
                    />
                  </label>
                </div>

                <div className="field-group">
                  <label className="cms-label">Kind</label>
                  <div className="role-selector">
                    {KIND_OPTS.map((k) => (
                      <button key={k} type="button"
                        className={`role-option${form.kind === k ? " active" : ""}`}
                        onClick={() => setForm((f) => ({ ...f, kind: k }))}
                      >{k}</button>
                    ))}
                  </div>
                </div>

                <div className="field-group">
                  <label className="cms-label">Veg type
                    <select
                      className="cms-textarea"
                      style={{ padding: "0.55rem 0.75rem", borderRadius: "8px" }}
                      value={form.vegType}
                      onChange={(e) => setForm((f) => ({ ...f, vegType: e.target.value }))}
                    >
                      {VEG_OPTS.map((o) => <option key={o.val} value={o.val}>{o.label}</option>)}
                    </select>
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

                {serverError && <p className="error-msg">{serverError}</p>}
                <button className="btn-primary" type="submit" disabled={saving || !form.name.trim()}>
                  {saving ? "Saving…" : isEdit ? "Save changes" : "Add category"}
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
