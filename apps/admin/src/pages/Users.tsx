import { useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { api } from "../lib/api";

type User = { id: string; username: string; role: string; createdAt: string; createdBy: string };

function validateUsername(v: string): string | null {
  if (!v.trim()) return "Username is required.";
  if (v.trim().length < 3) return "Minimum 3 characters.";
  if (v.trim().length > 50) return "Maximum 50 characters.";
  return null;
}

function validatePassword(v: string): string | null {
  if (!v) return "Password is required.";
  if (v.length < 8) return "Minimum 8 characters.";
  return null;
}

export function Users() {
  const [users, setUsers] = useState<User[]>([]);
  const [form, setForm] = useState({ username: "", password: "" });
  const [touched, setTouched] = useState({ username: false, password: false });
  const [serverError, setServerError] = useState("");
  const [creating, setCreating] = useState(false);

  const usernameErr = touched.username ? (validateUsername(form.username) ?? undefined) : undefined;
  const passwordErr = touched.password ? (validatePassword(form.password) ?? undefined) : undefined;

  function load() {
    api.get<User[]>("/admin/users").then(setUsers).catch(() => {});
  }

  useEffect(() => { load(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setTouched({ username: true, password: true });
    if (validateUsername(form.username) || validatePassword(form.password)) return;

    setServerError("");
    setCreating(true);
    try {
      await api.post("/admin/users", { username: form.username.trim(), password: form.password, role: "manager" });
      setForm({ username: "", password: "" });
      setTouched({ username: false, password: false });
      load();
    } catch (err: any) {
      setServerError(err?.message ?? "Failed to create manager.");
    } finally {
      setCreating(false);
    }
  }

  async function deleteUser(id: string, username: string) {
    if (!window.confirm(`Delete manager "${username}"?`)) return;
    await api.delete(`/admin/users/${id}`);
    load();
  }

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Managers" />
        <div className="page-body">
          <div className="users-split">
            <div className="users-list-col">
              <h2 className="section-heading">Active managers</h2>
              {users.length === 0 ? (
                <p className="empty-msg">No managers yet.</p>
              ) : (
                <div className="enquiry-list">
                  {users.map((u) => (
                    <div key={u.id} className="enquiry-card">
                      <div className="enquiry-header">
                        <div>
                          <strong>{u.username}</strong>
                          <span className="muted"> — {u.role}</span>
                        </div>
                        <button className="btn-action cancel" onClick={() => deleteUser(u.id, u.username)}>Remove</button>
                      </div>
                      <div className="enquiry-detail">
                        <span>Created by: {u.createdBy}</span>
                        <span>{new Date(u.createdAt).toLocaleDateString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="users-form-col">
              <h2 className="section-heading">Add manager</h2>
              <form className="user-form" onSubmit={handleCreate} noValidate>
                <div className="field-group">
                  <label className="cms-label">
                    Username
                    <input
                      className={`cms-textarea${usernameErr ? " input-error" : ""}`}
                      style={{ padding: "0.55rem 0.75rem", borderRadius: "8px", fontFamily: "inherit" }}
                      value={form.username}
                      onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
                      onBlur={() => setTouched((t) => ({ ...t, username: true }))}
                      placeholder="min 3 characters"
                    />
                  </label>
                  {usernameErr && <p className="field-error">{usernameErr}</p>}
                </div>

                <div className="field-group">
                  <label className="cms-label">
                    Password
                    <input
                      type="password"
                      className={`cms-textarea${passwordErr ? " input-error" : ""}`}
                      style={{ padding: "0.55rem 0.75rem", borderRadius: "8px", fontFamily: "inherit" }}
                      value={form.password}
                      onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                      onBlur={() => setTouched((t) => ({ ...t, password: true }))}
                      placeholder="min 8 characters"
                    />
                  </label>
                  {passwordErr && <p className="field-error">{passwordErr}</p>}
                </div>

                {serverError && <p className="error-msg">{serverError}</p>}
                <button className="btn-primary" type="submit" disabled={creating}>
                  {creating ? "Creating…" : "Add manager"}
                </button>
              </form>
              <p className="muted" style={{ fontSize: "0.82rem", marginTop: "1rem" }}>
                Managers can access all sections except this user management page.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
