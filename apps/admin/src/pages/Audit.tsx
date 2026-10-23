import { useCallback, useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { api } from "../lib/api";
import { SiteFooter } from "../components/SiteFooter";

type AuditEntry = {
  id: string; at: string; actor: string; actorRole: string | null; action: string;
  entityType: string | null; entityId: string | null; detail: string | null; ip: string | null;
};
type AuditPage = { items: AuditEntry[]; total: number };

const PAGE_SIZE = 50;

// Event groups the owner asks about most; each fills the "action contains" filter.
const QUICK = [
  { label: "All", value: "" },
  { label: "Logins", value: "login" },
  { label: "Refunds", value: "refund" },
  { label: "Bookings", value: "booking." },
  { label: "Users", value: "user." },
  { label: "Payments", value: "payment." },
];

function renderDetail(detail: string | null): string {
  if (!detail) return "";
  try {
    const obj = JSON.parse(detail);
    return Object.entries(obj)
      .filter(([, v]) => v !== null && v !== undefined)
      .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
      .join(" · ");
  } catch {
    return detail;
  }
}

export function Audit() {
  const [data, setData] = useState<AuditPage>({ items: [], total: 0 });
  const [action, setAction] = useState("");
  const [actor, setActor] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    const p = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
    if (action.trim()) p.set("action", action.trim());
    if (actor.trim()) p.set("actor", actor.trim());
    if (dateFrom) p.set("dateFrom", dateFrom);
    if (dateTo) p.set("dateTo", dateTo);
    setLoading(true);
    api.get<AuditPage>(`/admin/audit?${p}`)
      .then((d) => { setData(d); setError(""); })
      .catch((e) => setError(/superadmin|forbidden|admin access/i.test(e?.message ?? "")
        ? "Only the superadmin can view the audit log."
        : (e?.message ?? "Could not load the audit log.")))
      .finally(() => setLoading(false));
  }, [action, actor, dateFrom, dateTo, offset]);

  useEffect(() => { load(); }, [load]);

  function setFilter<T>(setter: (v: T) => void, v: T) {
    setter(v);
    setOffset(0); // a new filter always starts from the newest page
  }

  const from = data.total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, data.total);

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Audit log" />
        <div className="page-body">
          <div className="tab-bar">
            {QUICK.map((q) => (
              <button key={q.label} className={`tab-btn${action === q.value ? " active" : ""}`}
                onClick={() => setFilter(setAction, q.value)}>
                {q.label}
              </button>
            ))}
          </div>

          <div className="filter-bar" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
            <input data-testid="audit-action" className="cms-textarea" style={{ padding: "0.4rem 0.75rem", width: 180 }}
              placeholder="Action contains…" value={action} onChange={(e) => setFilter(setAction, e.target.value)} />
            <input data-testid="audit-actor" className="cms-textarea" style={{ padding: "0.4rem 0.75rem", width: 150 }}
              placeholder="Actor (exact)" value={actor} onChange={(e) => setFilter(setActor, e.target.value)} />
            <label className="muted" style={{ fontSize: "0.82rem" }}>From <input type="date" value={dateFrom} onChange={(e) => setFilter(setDateFrom, e.target.value)} /></label>
            <label className="muted" style={{ fontSize: "0.82rem" }}>To <input type="date" value={dateTo} onChange={(e) => setFilter(setDateTo, e.target.value)} /></label>
          </div>

          {error ? (
            <p className="error-msg" data-testid="audit-error">{error}</p>
          ) : data.items.length === 0 && !loading ? (
            <p className="empty-msg">No audit entries match.</p>
          ) : (
            <div className="table-wrap">
              <table data-testid="audit-table">
                <thead>
                  <tr><th>When</th><th>Actor</th><th>Action</th><th>Target</th><th>Details</th><th>IP</th></tr>
                </thead>
                <tbody>
                  {data.items.map((e) => (
                    <tr key={e.id}>
                      <td style={{ whiteSpace: "nowrap" }}>{new Date(e.at).toLocaleString()}</td>
                      <td>{e.actor}{e.actorRole && <span className="muted"> ({e.actorRole})</span>}</td>
                      <td><code>{e.action}</code></td>
                      <td className="muted">{e.entityType}{e.entityId ? ` · ${e.entityId.length > 12 ? e.entityId.slice(0, 8) + "…" : e.entityId}` : ""}</td>
                      <td style={{ maxWidth: 380, wordBreak: "break-word" }}>{renderDetail(e.detail)}</td>
                      <td className="muted">{e.ip}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {!error && (
            <div className="pagination-bar">
              <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>← Newer</button>
              <span data-testid="audit-range">{from}–{to} of {data.total}</span>
              <button disabled={offset + PAGE_SIZE >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)}>Older →</button>
            </div>
          )}
        </div>
        <SiteFooter />
      </div>
    </div>
  );
}
