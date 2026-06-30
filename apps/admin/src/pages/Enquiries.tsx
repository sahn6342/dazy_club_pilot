import { useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";

type Enquiry = {
  id: string; type: string; name: string; contact: string;
  company?: string; eventType?: string; estimatedGroupSize?: number;
  preferredDate?: string; preferredSport?: string; interestedSport?: string;
  message?: string; status: string; createdAt: string;
};

export function Enquiries() {
  const toast = useToast();
  const [enquiries, setEnquiries] = useState<Enquiry[]>([]);
  const [tab, setTab] = useState<"all" | "contact" | "corporate">("all");

  function load() {
    const q = tab !== "all" ? `?type=${tab}` : "";
    api.get<Enquiry[]>(`/admin/enquiries${q}`).then(setEnquiries).catch(() => {});
  }

  useEffect(() => { load(); }, [tab]);

  async function markHandled(id: string) {
    await api.patch(`/admin/enquiries/${id}`, { status: "handled" });
    load();
    toast.success("Marked as handled");
  }

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Enquiries" />
        <div className="page-body">
          <div className="tab-bar">
            {(["all", "contact", "corporate"] as const).map((t) => (
              <button key={t} className={`tab-btn${tab === t ? " active" : ""}`} onClick={() => setTab(t)}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
          {enquiries.length === 0 ? (
            <p className="empty-msg">No enquiries yet.</p>
          ) : (
            <div className="enquiry-list">
              {enquiries.map((e) => (
                <div key={e.id} className="enquiry-card">
                  <div className="enquiry-header">
                    <div>
                      <strong>{e.name}</strong>
                      {e.company && <span className="muted"> — {e.company}</span>}
                    </div>
                    <div className="enquiry-meta">
                      <span className="type-badge">{e.type}</span>
                      <StatusBadge status={e.status} />
                    </div>
                  </div>
                  <div className="enquiry-detail">
                    <span>{e.contact}</span>
                    {e.interestedSport && <span>Sport: {e.interestedSport}</span>}
                    {e.preferredSport && <span>Sport: {e.preferredSport}</span>}
                    {e.estimatedGroupSize && <span>Group size: {e.estimatedGroupSize}</span>}
                    {e.preferredDate && <span>Date: {e.preferredDate}</span>}
                  </div>
                  {e.message && <p className="enquiry-message">"{e.message}"</p>}
                  <div className="enquiry-footer">
                    <small className="muted">{new Date(e.createdAt).toLocaleString()}</small>
                    {e.status === "new" && (
                      <button className="btn-action confirm" onClick={() => markHandled(e.id)}>Mark handled</button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
