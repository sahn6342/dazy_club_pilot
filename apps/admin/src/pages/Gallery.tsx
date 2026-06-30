import { useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/Toast";
import { api, resolveImg } from "../lib/api";

type GalleryItem = { id: string; title: string; sportSlug: string; tone: string; imageUrl: string | null; approved: boolean };

const SPORTS = ["cricket", "badminton", "pickleball"];
const EMPTY = { title: "", sportSlug: "cricket", tone: "", imageUrl: "" };

function Thumb({ url, alt }: { url: string | null; alt: string }) {
  const src = resolveImg(url);
  if (!src) return <div className="gallery-thumb" />;
  return <img className="gallery-thumb" src={src} alt={alt} loading="lazy" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />;
}

export function Gallery() {
  const toast = useToast();
  const [items, setItems] = useState<GalleryItem[]>([]);
  const [form, setForm] = useState({ ...EMPTY });
  const [uploading, setUploading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [editId, setEditId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState({ ...EMPTY });

  function load() {
    api.get<GalleryItem[]>("/admin/gallery").then(setItems).catch((e) => setError(e.message));
  }
  useEffect(() => { load(); }, []);

  async function setApproved(id: string, approved: boolean) {
    await api.patch(`/admin/gallery/${id}`, { approved });
    load();
    toast.success(approved ? "Item approved" : "Item rejected");
  }
  async function deleteItem(id: string) {
    if (!window.confirm("Delete this gallery item?")) return;
    await api.delete(`/admin/gallery/${id}`);
    load();
    toast.success("Item deleted");
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>, target: "create" | "edit") {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    setUploading(true);
    try {
      const res = await api.upload<{ imageUrl: string }>("/admin/gallery/upload", file);
      if (target === "create") setForm((f) => ({ ...f, imageUrl: res.imageUrl }));
      else setEditDraft((d) => ({ ...d, imageUrl: res.imageUrl }));
    } catch (err: any) {
      setError(err?.message ?? "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!form.title.trim() || !form.tone.trim()) { setError("Title and tone are required."); return; }
    setCreating(true);
    try {
      await api.post("/admin/gallery", {
        title: form.title.trim(), sportSlug: form.sportSlug, tone: form.tone.trim(),
        imageUrl: form.imageUrl.trim() || null, approved: true,
      });
      setForm({ ...EMPTY });
      load();
      toast.success("Gallery item added");
    } catch (err: any) {
      setError(err?.message ?? "Failed to create item.");
      toast.error(err?.message ?? "Failed to create item");
    } finally {
      setCreating(false);
    }
  }

  function startEdit(item: GalleryItem) {
    setEditId(item.id);
    setEditDraft({ title: item.title, sportSlug: item.sportSlug, tone: item.tone, imageUrl: item.imageUrl ?? "" });
  }
  async function saveEdit(id: string) {
    try {
      await api.patch(`/admin/gallery/${id}`, {
        title: editDraft.title.trim(), sportSlug: editDraft.sportSlug,
        tone: editDraft.tone.trim(), imageUrl: editDraft.imageUrl.trim() || null,
      });
      setEditId(null);
      load();
      toast.success("Gallery item updated");
    } catch (err: any) {
      toast.error(err?.message ?? "Failed to update item");
    }
  }

  const inputStyle = { padding: "0.5rem 0.65rem", borderRadius: "8px", fontFamily: "inherit", width: "100%" };

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Gallery" />
        <div className="page-body">
          {error && <p className="error-msg">{error}</p>}

          {/* Create form */}
          <form className="user-form" onSubmit={create} style={{ maxWidth: 520, marginBottom: "1.5rem" }}>
            <h2 className="section-heading">Add gallery item</h2>
            <div className="field-group">
              <label className="cms-label">Title
                <input className="cms-textarea" style={inputStyle} data-testid="gallery-title" maxLength={120} value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} placeholder="e.g. Evening turf sessions" />
              </label>
            </div>
            <div className="field-group">
              <label className="cms-label">Sport
                <select className="cms-textarea" style={inputStyle} data-testid="gallery-sport" value={form.sportSlug} onChange={(e) => setForm((f) => ({ ...f, sportSlug: e.target.value }))}>
                  {SPORTS.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </label>
            </div>
            <div className="field-group">
              <label className="cms-label">Tone
                <input className="cms-textarea" style={inputStyle} data-testid="gallery-tone" maxLength={60} value={form.tone} onChange={(e) => setForm((f) => ({ ...f, tone: e.target.value }))} placeholder="e.g. electric" />
              </label>
            </div>
            <div className="field-group">
              <label className="cms-label">Image URL (paste a link)
                <input className="cms-textarea" style={inputStyle} data-testid="gallery-image-url" value={form.imageUrl} onChange={(e) => setForm((f) => ({ ...f, imageUrl: e.target.value }))} placeholder="https://… or upload below" />
              </label>
            </div>
            <div className="field-group">
              <label className="cms-label">…or upload a file
                <input type="file" accept="image/*" data-testid="gallery-image-file" onChange={(e) => onFile(e, "create")} disabled={uploading} />
              </label>
              {uploading && <span className="muted">Uploading…</span>}
              {form.imageUrl && <Thumb url={form.imageUrl} alt="preview" />}
            </div>
            <button className="btn-primary" type="submit" data-testid="gallery-submit" disabled={creating || uploading}>
              {creating ? "Adding…" : "Add item"}
            </button>
          </form>

          {/* Existing items */}
          <div className="card-grid-admin">
            {items.map((item) => (
              <div key={item.id} className="gallery-card" data-id={item.id}>
                {editId === item.id ? (
                  <div className="gallery-info" style={{ paddingTop: "0.85rem", gap: "0.5rem" }}>
                    <input className="cms-textarea" style={inputStyle} maxLength={120} value={editDraft.title} onChange={(e) => setEditDraft((d) => ({ ...d, title: e.target.value }))} placeholder="Title" />
                    <select className="cms-textarea" style={inputStyle} value={editDraft.sportSlug} onChange={(e) => setEditDraft((d) => ({ ...d, sportSlug: e.target.value }))}>
                      {SPORTS.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                    <input className="cms-textarea" style={inputStyle} maxLength={60} value={editDraft.tone} onChange={(e) => setEditDraft((d) => ({ ...d, tone: e.target.value }))} placeholder="Tone" />
                    <input className="cms-textarea" style={inputStyle} value={editDraft.imageUrl} onChange={(e) => setEditDraft((d) => ({ ...d, imageUrl: e.target.value }))} placeholder="Image URL" />
                    <input type="file" accept="image/*" onChange={(e) => onFile(e, "edit")} disabled={uploading} />
                    <div className="action-row">
                      <button className="btn-action confirm" data-testid="gallery-edit-save" onClick={() => saveEdit(item.id)}>Save</button>
                      <button className="btn-action secondary" onClick={() => setEditId(null)}>Cancel</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <Thumb url={item.imageUrl} alt={item.title} />
                    <div className="gallery-info">
                      <strong>{item.title}</strong>
                      <span className="muted" style={{ textTransform: "capitalize" }}>{item.sportSlug} · {item.tone}</span>
                      <StatusBadge status={item.approved ? "approved" : "rejected"} />
                    </div>
                    <div className="action-row">
                      <button className="btn-action confirm" onClick={() => setApproved(item.id, true)} disabled={item.approved}>Approve</button>
                      <button className="btn-action cancel" onClick={() => setApproved(item.id, false)} disabled={!item.approved}>Reject</button>
                      <button className="btn-action secondary" data-testid="gallery-edit" onClick={() => startEdit(item)}>Edit</button>
                      <button className="btn-action delete" onClick={() => deleteItem(item.id)}>Delete</button>
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
