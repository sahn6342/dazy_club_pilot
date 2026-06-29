import { useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { StatusBadge } from "../components/StatusBadge";
import { api } from "../lib/api";

type Testimonial = { id: string; name: string; context: string; quote: string; approved: boolean };

export function Testimonials() {
  const [items, setItems] = useState<Testimonial[]>([]);

  function load() {
    api.get<Testimonial[]>("/admin/testimonials").then(setItems).catch(() => {});
  }

  useEffect(() => { load(); }, []);

  async function setApproved(id: string, approved: boolean) {
    await api.patch(`/admin/testimonials/${id}`, { approved });
    load();
  }

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Testimonials" />
        <div className="page-body">
          <div className="enquiry-list">
            {items.map((t) => (
              <div key={t.id} className="enquiry-card">
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
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
