import { useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { useConfirm } from "../components/ConfirmDialog";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";

type CmsEntry = { key: string; label: string; value: string };

const inputStyle = { padding: "0.5rem 0.65rem", borderRadius: "8px", fontFamily: "inherit", width: "100%" };

export function CMS() {
  const confirm = useConfirm();
  const toast = useToast();
  const [entries, setEntries] = useState<CmsEntry[]>([]);
  const [editVal, setEditVal] = useState<Record<string, string>>({});
  const [editLabel, setEditLabel] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState<Record<string, boolean>>({});
  const [form, setForm] = useState({ key: "", label: "", value: "" });
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);

  function load() {
    api.get<CmsEntry[]>("/admin/cms").then((data) => {
      setEntries(data);
      setEditVal(Object.fromEntries(data.map((e) => [e.key, e.value])));
      setEditLabel(Object.fromEntries(data.map((e) => [e.key, e.label])));
    }).catch((e) => setError(e.message));
  }
  useEffect(() => { load(); }, []);

  async function save(key: string) {
    try {
      await api.put(`/admin/cms/${key}`, { value: editVal[key], label: editLabel[key] });
      setSaved((s) => ({ ...s, [key]: true }));
      setTimeout(() => setSaved((s) => ({ ...s, [key]: false })), 2000);
      load();
      toast.success("Content saved");
    } catch (err: any) {
      toast.error(err?.message ?? "Failed to save content");
    }
  }

  async function remove(key: string) {
    if (!await confirm({ message: "Delete this CMS entry?", confirmLabel: "Delete", danger: true })) return;
    try {
      await api.delete(`/admin/cms/${key}`);
      load();
      toast.success("Entry deleted");
    } catch (err: any) {
      toast.error(err?.message ?? "Failed to delete entry");
    }
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!/^[a-z0-9_]+$/.test(form.key)) { setError("Key must be lowercase letters, numbers, underscores."); return; }
    if (!form.label.trim() || !form.value.trim()) { setError("Label and value are required."); return; }
    setCreating(true);
    try {
      await api.post("/admin/cms", { key: form.key, label: form.label.trim(), value: form.value.trim() });
      setForm({ key: "", label: "", value: "" });
      load();
      toast.success("Entry added");
    } catch (err: any) {
      setError(err?.message ?? "Failed to create entry.");
      toast.error(err?.message ?? "Failed to create entry");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Content (CMS)" />
        <div className="page-body">
          {error && <p className="error-msg">{error}</p>}

          {/* Create form */}
          <form className="user-form" onSubmit={create} style={{ maxWidth: 700, marginBottom: "1.5rem" }}>
            <h2 className="section-heading">Add content entry</h2>
            <div className="field-group">
              <label className="cms-label">Key (lowercase_with_underscores)
                <input className="cms-textarea" style={inputStyle} data-testid="cms-new-key" maxLength={60} value={form.key} onChange={(e) => setForm((f) => ({ ...f, key: e.target.value.toLowerCase() }))} placeholder="e.g. faq_parking" />
              </label>
            </div>
            <div className="field-group">
              <label className="cms-label">Label
                <input className="cms-textarea" style={inputStyle} data-testid="cms-new-label" maxLength={120} value={form.label} onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))} placeholder="e.g. FAQ: Parking" />
              </label>
            </div>
            <div className="field-group">
              <label className="cms-label">Value
                <textarea className="cms-textarea" style={inputStyle} rows={3} data-testid="cms-new-value" value={form.value} onChange={(e) => setForm((f) => ({ ...f, value: e.target.value }))} placeholder="Content…" />
              </label>
            </div>
            <button className="btn-primary" type="submit" data-testid="cms-create" disabled={creating}>
              {creating ? "Adding…" : "Add entry"}
            </button>
          </form>

          <div className="cms-list">
            {entries.map((entry) => (
              <div key={entry.key} className="cms-entry" data-key={entry.key}>
                <input
                  className="cms-label cms-textarea"
                  style={{ ...inputStyle, fontWeight: 600, marginBottom: "0.4rem" }}
                  maxLength={120}
                  value={editLabel[entry.key] ?? ""}
                  onChange={(e) => setEditLabel((l) => ({ ...l, [entry.key]: e.target.value }))}
                />
                <textarea
                  className="cms-textarea"
                  value={editVal[entry.key] ?? ""}
                  rows={(editVal[entry.key]?.length ?? 0) > 100 ? 4 : 2}
                  onChange={(e) => setEditVal((ed) => ({ ...ed, [entry.key]: e.target.value }))}
                />
                <div className="cms-actions">
                  <button className="btn-primary small" onClick={() => save(entry.key)}>Save</button>
                  <button className="btn-action delete" data-testid="cms-delete" onClick={() => remove(entry.key)}>Delete</button>
                  {saved[entry.key] && <span className="saved-msg">Saved ✓</span>}
                  <span className="muted" style={{ fontSize: "0.75rem", marginLeft: "0.5rem" }}>{entry.key}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
