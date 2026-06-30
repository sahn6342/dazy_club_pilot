import { useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { useConfirm } from "../components/ConfirmDialog";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";

type Category = { id: string; name: string; active: boolean };
type Item = { id: string; category_id: string; name: string; description: string | null; price: number; taxRatePercent: number; vegType: string | null; station: string; available: boolean; sortOrder: number };

const VEG_OPTS = [{ val: "", label: "— none —" }, { val: "veg", label: "Veg" }, { val: "nonveg", label: "Non-veg" }, { val: "egg", label: "Egg" }, { val: "na", label: "N/A" }];
const STATION_OPTS = ["kitchen", "bar", "none"];

const EMPTY_FORM = { category_id: "", name: "", description: "", price: "", taxRatePercent: "5", vegType: "", station: "kitchen", available: true, sortOrder: 0 };

export function CafeItems() {
  const confirm = useConfirm();
  const toast = useToast();
  const [cats, setCats] = useState<Category[]>([]);
  const [items, setItems] = useState<Item[]>([]);
  const [filterCat, setFilterCat] = useState("all");
  const [form, setForm] = useState(EMPTY_FORM);
  const [editTarget, setEditTarget] = useState<Item | null>(null);
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState("");

  const isEdit = !!editTarget;

  function load() {
    api.get<Category[]>("/admin/cafe/categories").then((c) => {
      setCats(c);
      setForm((f) => f.category_id ? f : { ...f, category_id: c[0]?.id ?? "" });
    }).catch(() => {});
    api.get<Item[]>("/admin/cafe/items").then(setItems).catch(() => {});
  }
  useEffect(() => { load(); }, []);

  function startCreate() {
    setEditTarget(null);
    setForm((f) => ({ ...EMPTY_FORM, category_id: cats[0]?.id ?? "" }));
    setServerError("");
  }

  function startEdit(item: Item) {
    setEditTarget(item);
    setForm({
      category_id: item.category_id,
      name: item.name,
      description: item.description ?? "",
      price: String(item.price),
      taxRatePercent: String(item.taxRatePercent),
      vegType: item.vegType ?? "",
      station: item.station,
      available: item.available,
      sortOrder: item.sortOrder,
    });
    setServerError("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim() || !form.category_id || form.price === "") return;
    setSaving(true);
    setServerError("");
    const payload = {
      category_id: form.category_id,
      name: form.name.trim(),
      description: form.description || null,
      price: Number(form.price),
      taxRatePercent: Number(form.taxRatePercent),
      vegType: form.vegType || null,
      station: form.station,
      available: form.available,
      sortOrder: form.sortOrder,
    };
    try {
      if (isEdit) {
        await api.patch(`/admin/cafe/items/${editTarget!.id}`, payload);
        toast.success("Item updated");
      } else {
        await api.post("/admin/cafe/items", payload);
        toast.success("Item added");
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

  async function toggleAvailable(item: Item) {
    try {
      await api.patch(`/admin/cafe/items/${item.id}`, { available: !item.available });
      load();
    } catch (err: any) { toast.error(err?.message ?? "Failed"); }
  }

  async function handleDelete(item: Item) {
    if (!await confirm({ message: "Delete this menu item?", confirmLabel: "Delete", danger: true })) return;
    try {
      await api.delete(`/admin/cafe/items/${item.id}`);
      toast.success("Deleted");
      if (editTarget?.id === item.id) startCreate();
      load();
    } catch (err: any) { toast.error(err?.message ?? "Delete failed"); }
  }

  const catName = (id: string) => cats.find((c) => c.id === id)?.name ?? "—";
  const visible = filterCat === "all" ? items : items.filter((i) => i.category_id === filterCat);

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Menu Items" />
        <div className="page-body">
          <div className="users-split">

            <div className="users-list-col">
              <div className="tab-pills" style={{ marginBottom: "1rem", flexWrap: "wrap" }}>
                <button className={`court-pill${filterCat === "all" ? " active" : ""}`} onClick={() => setFilterCat("all")}>
                  All <span style={{ marginLeft: "0.3rem", opacity: 0.6, fontSize: "0.75rem" }}>{items.length}</span>
                </button>
                {cats.map((c) => (
                  <button key={c.id} className={`court-pill${filterCat === c.id ? " active" : ""}`} onClick={() => setFilterCat(c.id)}>
                    {c.name} <span style={{ marginLeft: "0.3rem", opacity: 0.6, fontSize: "0.75rem" }}>{items.filter((i) => i.category_id === c.id).length}</span>
                  </button>
                ))}
              </div>

              {visible.length === 0 ? (
                <p className="empty-msg">No items{filterCat !== "all" ? " in this category" : ""} yet.</p>
              ) : (
                <div className="enquiry-list">
                  {visible.map((item) => (
                    <div key={item.id}
                      className={`enquiry-card${editTarget?.id === item.id ? " selected-card" : ""}`}
                      style={{ cursor: "pointer", opacity: item.available ? 1 : 0.55 }}
                      onClick={() => startEdit(item)}
                    >
                      <div className="enquiry-header">
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                          <strong>{item.name}</strong>
                          <span style={{ color: "var(--gold)", fontWeight: 600, fontSize: "0.9rem" }}>₹{item.price}</span>
                          {!item.available && <span className="role-badge" style={{ background: "rgba(100,100,100,0.15)", color: "#888" }}>hidden</span>}
                        </div>
                        <div style={{ display: "flex", gap: "0.4rem" }}>
                          <button className="btn-action secondary" onClick={(e) => { e.stopPropagation(); toggleAvailable(item); }}>
                            {item.available ? "Hide" : "Show"}
                          </button>
                          <button className="btn-action cancel" onClick={(e) => { e.stopPropagation(); handleDelete(item); }}>Delete</button>
                        </div>
                      </div>
                      <div className="enquiry-detail">
                        <span>{catName(item.category_id)}</span>
                        <span>{item.station} · {item.taxRatePercent}% tax</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="users-form-col">
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
                <h2 className="section-heading" style={{ margin: 0 }}>
                  {isEdit ? `Edit — ${editTarget?.name}` : "Add item"}
                </h2>
                {isEdit && <button className="btn-action secondary" onClick={startCreate}>+ New</button>}
              </div>

              <form className="user-form" onSubmit={handleSubmit} noValidate>
                <div className="field-group">
                  <label className="cms-label">Category
                    <select
                      className="cms-textarea"
                      style={{ padding: "0.55rem 0.75rem", borderRadius: "8px" }}
                      value={form.category_id}
                      onChange={(e) => setForm((f) => ({ ...f, category_id: e.target.value }))}
                    >
                      <option value="">— select category —</option>
                      {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                  </label>
                </div>

                <div className="field-group">
                  <label className="cms-label">Name
                    <input
                      className="cms-textarea"
                      style={{ padding: "0.55rem 0.75rem", borderRadius: "8px", fontFamily: "inherit" }}
                      value={form.name}
                      onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                      placeholder="Item name"
                      required
                    />
                  </label>
                </div>

                <div className="field-group">
                  <label className="cms-label">Description
                    <input
                      className="cms-textarea"
                      style={{ padding: "0.55rem 0.75rem", borderRadius: "8px", fontFamily: "inherit" }}
                      value={form.description}
                      onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                      placeholder="Short description (optional)"
                    />
                  </label>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div className="field-group">
                    <label className="cms-label">Price (₹)
                      <input
                        type="number" min="0" step="0.5"
                        className="cms-textarea"
                        style={{ padding: "0.55rem 0.75rem", borderRadius: "8px", fontFamily: "inherit" }}
                        value={form.price}
                        onChange={(e) => setForm((f) => ({ ...f, price: e.target.value }))}
                        placeholder="0"
                        required
                      />
                    </label>
                  </div>
                  <div className="field-group">
                    <label className="cms-label">Tax %
                      <input
                        type="number" min="0" max="100" step="0.5"
                        className="cms-textarea"
                        style={{ padding: "0.55rem 0.75rem", borderRadius: "8px", fontFamily: "inherit" }}
                        value={form.taxRatePercent}
                        onChange={(e) => setForm((f) => ({ ...f, taxRatePercent: e.target.value }))}
                      />
                    </label>
                  </div>
                </div>

                <div className="field-group">
                  <label className="cms-label">Station</label>
                  <div className="role-selector">
                    {STATION_OPTS.map((s) => (
                      <button key={s} type="button"
                        className={`role-option${form.station === s ? " active" : ""}`}
                        onClick={() => setForm((f) => ({ ...f, station: s }))}
                      >{s}</button>
                    ))}
                  </div>
                  <p className="muted" style={{ fontSize: "0.78rem", marginTop: "0.3rem" }}>
                    {form.station === "kitchen" ? "Printed on kitchen ticket." : form.station === "bar" ? "Printed on bar ticket." : "No ticket printed."}
                  </p>
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

                <div className="field-group" style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                  <input type="checkbox" id="avail-chk" checked={form.available}
                    onChange={(e) => setForm((f) => ({ ...f, available: e.target.checked }))} />
                  <label htmlFor="avail-chk" className="cms-label" style={{ margin: 0, cursor: "pointer" }}>
                    Available on kiosk
                  </label>
                </div>

                {serverError && <p className="error-msg">{serverError}</p>}
                <button className="btn-primary" type="submit" disabled={saving || !form.name.trim() || !form.category_id || form.price === ""}>
                  {saving ? "Saving…" : isEdit ? "Save changes" : "Add item"}
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
