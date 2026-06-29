import { useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { StatusBadge } from "../components/StatusBadge";
import { api } from "../lib/api";

type GalleryItem = { id: string; title: string; sportSlug: string; tone: string; approved: boolean };

export function Gallery() {
  const [items, setItems] = useState<GalleryItem[]>([]);

  function load() {
    api.get<GalleryItem[]>("/admin/gallery").then(setItems).catch(() => {});
  }

  useEffect(() => { load(); }, []);

  async function setApproved(id: string, approved: boolean) {
    await api.patch(`/admin/gallery/${id}`, { approved });
    load();
  }

  async function deleteItem(id: string) {
    await api.delete(`/admin/gallery/${id}`);
    load();
  }

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Gallery" />
        <div className="page-body">
          <div className="card-grid-admin">
            {items.map((item) => (
              <div key={item.id} className="gallery-card">
                <div className="gallery-thumb" />
                <div className="gallery-info">
                  <strong>{item.title}</strong>
                  <span className="muted" style={{ textTransform: "capitalize" }}>{item.sportSlug} · {item.tone}</span>
                  <StatusBadge status={item.approved ? "approved" : "rejected"} />
                </div>
                <div className="action-row">
                  <button className="btn-action confirm" onClick={() => setApproved(item.id, true)} disabled={item.approved}>Approve</button>
                  <button className="btn-action cancel" onClick={() => setApproved(item.id, false)} disabled={!item.approved}>Reject</button>
                  <button className="btn-action delete" onClick={() => deleteItem(item.id)}>Delete</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
