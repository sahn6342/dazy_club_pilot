import { useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";

type Testimonial = { id: string; name: string; context: string; quote: string; approved: boolean };

const EMPTY = { name: "", context: "", quote: "" };
const inputStyle = { padding: "0.5rem 0.65rem", borderRadius: "8px", fontFamily: "inherit", width: "100%" };

export function Testimonials() {
  const toast = useToast();
  const [items, setItems] = useState<Testimonial[]>([]);
  const [form, setForm] = useState({ ...EMPTY });
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [editId, setEditId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState({ ...EMPTY });

  function load() {
    api.get<Testimonial[]>("/admin/testimonials").then(setItems).catch((e) => setError(e.message));
  }
  useEffect(() => { load(); }, []);

  async function setApproved(id: string, approved: boolean) {
    await api.patch(`/admin/testimonials/${id}`, { approved });
    load();
    toast.success(approved ? "Testimonial approved" : "Testimonial rejected");
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!form.name.trim() || !form.context.trim() || !form.quote.trim()) {
      setError("Name, context, and quote are required."); return;
    }
    setCreating(true);
    try {
      await api.post("/admin/testimonials", {
        name: form.name.trim(), context: form.context.trim(), quote: form.quote.trim(), approved: true,
      });
      setForm({ ...EMPTY });
      load();
      toast.success("Testimonial added");
    } catch (err: any) {
      setError(err?.message ?? "Failed to create testimonial.");
      toast.error(err?.message ?? "Failed to create testimonial");
    } finally {
      setCreating(false);
    }
  }

  function startEdit(t: Testimonial) {
    setEditId(t.id);
    setEditDraft({ name: t.name, context: t.context, quote: t.quote });
  }
  async function saveEdit(id: string) {
    try {
      await api.put(`/admin/testimonials/${id}`, {
        name: editDraft.name.trim(), context: editDraft.context.trim(), quote: editDraft.quote.trim(),
      });
      setEditId(null);
      load();
      toast.success("Testimonial updated");
    } catch (err: any) {
      toast.error(err?.message ?? "Failed to update testimonial");
    }
  }
  async function deleteItem(id: string) {
    if (!window.confirm("Delete this testimonial?")) return;
    await api.delete(`/admin/testimonials/${id}`);
    load();
    toast.success("Testimonial deleted");
  }

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Testimonials" />
        <div className="page-body">
          {error && <p className="error-msg">{error}</p>}

          {/* Create form */}
          <form className="user-form" onSubmit={create} style={{ maxWidth: 560, marginBottom: "1.5rem" }}>
            <h2 className="section-heading">Add testimonial</h2>
            <div className="field-group">
              <label className="cms-label">Name
                <input className="cms-textarea" style={inputStyle} data-testid="testimonial-name" maxLength={80} value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="e.g. Priya R." />
              </label>
            </div>
            <div className="field-group">
              <label className="cms-label">Context
                <input className="cms-textarea" style={inputStyle} data-testid="testimonial-context" maxLength={120} value={form.context} onChange={(e) => setForm((f) => ({ ...f, context: e.target.value }))} placeholder="e.g. Weekend player" />
              </label>
            </div>
            <div className="field-group">
              <label className="cms-label">Quote
                <textarea className="cms-textarea" style={inputStyle} rows={3} data-testid="testimonial-quote" maxLength={500} value={form.quote} onChange={(e) => setForm((f) => ({ ...f, quote: e.target.value }))} placeholder="What they said…" />
              </label>
            </div>
            <button className="btn-primary" type="submit" data-testid="testimonial-submit" disabled={creating}>
              {creating ? "Adding…" : "Add testimonial"}
            </button>
          </form>

          <div className="enquiry-list">
            {items.map((t) => (
              <div key={t.id} className="enquiry-card" data-id={t.id}>
                {editId === t.id ? (
                  <div className="field-group" style={{ gap: "0.5rem", display: "flex", flexDirection: "column" }}>
                    <input className="cms-textarea" style={inputStyle} maxLength={80} value={editDraft.name} onChange={(e) => setEditDraft((d) => ({ ...d, name: e.target.value }))} placeholder="Name" />
                    <input className="cms-textarea" style={inputStyle} maxLength={120} value={editDraft.context} onChange={(e) => setEditDraft((d) => ({ ...d, context: e.target.value }))} placeholder="Context" />
                    <textarea className="cms-textarea" style={inputStyle} rows={3} maxLength={500} value={editDraft.quote} onChange={(e) => setEditDraft((d) => ({ ...d, quote: e.target.value }))} placeholder="Quote" />
                    <div className="action-row">
                      <button className="btn-action confirm" data-testid="testimonial-edit-save" onClick={() => saveEdit(t.id)}>Save</button>
                      <button className="btn-action secondary" onClick={() => setEditId(null)}>Cancel</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="enquiry-header">
                      <div>
                        <strong>{t.name}</strong>
                        <span className="muted"> — {t.context}</span>
                      </div>
                      <StatusBadge status={t.approved ? "approved" : "rejected"} />
                    </div>
                    <p className="enquiry-message">"{t.quote}"</p>
                    <div className="action-row">
                      <button className="btn-action confirm" onClick={() => setApproved(t.id, true)} disabled={t.approved}>Approve</button>
                      <button className="btn-action cancel" onClick={() => setApproved(t.id, false)} disabled={!t.approved}>Reject</button>
                      <button className="btn-action secondary" data-testid="testimonial-edit" onClick={() => startEdit(t)}>Edit</button>
                      <button className="btn-action delete" onClick={() => deleteItem(t.id)}>Delete</button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
