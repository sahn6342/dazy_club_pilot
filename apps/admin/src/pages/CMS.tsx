import { useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { api } from "../lib/api";

type CmsEntry = { key: string; label: string; value: string };

export function CMS() {
  const [entries, setEntries] = useState<CmsEntry[]>([]);
  const [editing, setEditing] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState<Record<string, boolean>>({});

  useEffect(() => {
    api.get<CmsEntry[]>("/admin/cms").then((data) => {
      setEntries(data);
      setEditing(Object.fromEntries(data.map((e) => [e.key, e.value])));
    }).catch(() => {});
  }, []);

  async function save(key: string) {
    await api.put(`/admin/cms/${key}`, { value: editing[key] });
    setSaved((s) => ({ ...s, [key]: true }));
    setTimeout(() => setSaved((s) => ({ ...s, [key]: false })), 2000);
  }

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Content (CMS)" />
        <div className="page-body">
          <div className="cms-list">
            {entries.map((entry) => (
              <div key={entry.key} className="cms-entry">
                <label className="cms-label">{entry.label}</label>
                <textarea
                  className="cms-textarea"
                  value={editing[entry.key] ?? ""}
                  rows={entry.value.length > 100 ? 4 : 2}
                  onChange={(e) => setEditing((ed) => ({ ...ed, [entry.key]: e.target.value }))}
                />
                <div className="cms-actions">
                  <button className="btn-primary small" onClick={() => save(entry.key)}>Save</button>
                  {saved[entry.key] && <span className="saved-msg">Saved ✓</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
