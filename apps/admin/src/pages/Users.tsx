import { useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { useConfirm } from "../components/ConfirmDialog";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";

type User = { id: string; username: string; role: string; createdAt: string; createdBy: string };
type Tab = "all" | "manager" | "staff";
type FormMode = "create" | "edit";

const ROLE_LABEL: Record<string, string> = { manager: "Manager", cashier: "Cashier", kitchen: "Kitchen" };
const ROLE_BADGE: Record<string, string> = { manager: "badge-manager", cashier: "badge-cashier", kitchen: "badge-kitchen" };

function validateUsername(v: string) {
  if (!v.trim()) return "Required.";
  if (v.trim().length < 3) return "Min 3 characters.";
  if (v.trim().length > 50) return "Max 50 characters.";
  if (!/^[a-zA-Z0-9_]+$/.test(v.trim())) return "Letters, numbers, underscores only.";
  return null;
}

function validatePassword(v: string, role: string) {
  if (!v) return null; // blank = no change on edit
  if (role === "manager" && v.length < 8) return "Manager password min 8 characters.";
  if (role !== "manager" && (!/^\d{4}$/.test(v))) return "Staff PIN must be exactly 4 digits.";
  return null;
}

const EMPTY_FORM = { username: "", password: "", role: "manager" };

export function Users() {
  const confirm = useConfirm();
  const toast = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [tab, setTab] = useState<Tab>("all");
  const [mode, setMode] = useState<FormMode>("create");
  const [editTarget, setEditTarget] = useState<User | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [touched, setTouched] = useState({ username: false, password: false });
  const [serverError, setServerError] = useState("");
  const [saving, setSaving] = useState(false);

  const isEdit = mode === "edit";
  const isStaffRole = form.role !== "manager";

  const usernameErr = touched.username && !isEdit ? validateUsername(form.username) : null;
  const passwordErr = touched.password ? validatePassword(form.password, form.role) : null;

  function load() {
    api.get<User[]>("/admin/users").then(setUsers).catch(() => {});
  }

  useEffect(() => { load(); }, []);

  function startCreate() {
    setMode("create");
    setEditTarget(null);
    setForm(EMPTY_FORM);
    setTouched({ username: false, password: false });
    setServerError("");
  }

  function startEdit(u: User) {
    setMode("edit");
    setEditTarget(u);
    setForm({ username: u.username, password: "", role: u.role });
    setTouched({ username: false, password: false });
    setServerError("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isEdit) setTouched({ username: true, password: true });
    else setTouched((t) => ({ ...t, password: true }));

    if (!isEdit && validateUsername(form.username)) return;
    if (form.password && validatePassword(form.password, form.role)) return;
    if (!isEdit && !form.password) return; // password required on create

    setSaving(true);
    setServerError("");
    try {
      if (isEdit && editTarget) {
        const body: Record<string, string> = { role: form.role };
        if (form.password) body.password = form.password;
        await api.patch(`/admin/users/${editTarget.id}`, body);
        toast.success("User updated");
      } else {
        await api.post("/admin/users", {
          username: form.username.trim(),
          password: form.password,
          role: form.role,
        });
        toast.success(`${ROLE_LABEL[form.role]} added`);
      }
      startCreate();
      load();
    } catch (err: any) {
      setServerError(err?.message ?? "Failed.");
      toast.error(err?.message ?? "Failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(u: User) {
    if (!await confirm({ message: `Remove user "${u.username}"? This cannot be undone.`, confirmLabel: "Remove", danger: true })) return;
    try {
      await api.delete(`/admin/users/${u.id}`);
      toast.success("User removed");
      if (editTarget?.id === u.id) startCreate();
      load();
    } catch (err: any) {
      toast.error(err?.message ?? "Delete failed");
    }
  }

  const visible = users.filter((u) => {
    if (tab === "manager") return u.role === "manager";
    if (tab === "staff") return u.role === "cashier" || u.role === "kitchen";
    return true;
  });

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Manage Users" />
        <div className="page-body">
          <div className="users-split">

            {/* ── Left: list ── */}
            <div className="users-list-col">
              <div className="tab-pills" style={{ marginBottom: "1rem" }}>
                {(["all", "manager", "staff"] as Tab[]).map((t) => (
                  <button
                    key={t}
                    className={`court-pill${tab === t ? " active" : ""}`}
                    onClick={() => setTab(t)}
                  >
                    {t === "all" ? "All" : t === "manager" ? "Managers" : "Kiosk Staff"}
                    <span style={{ marginLeft: "0.4rem", opacity: 0.6, fontSize: "0.75rem" }}>
                      {t === "all" ? users.length
                        : t === "manager" ? users.filter((u) => u.role === "manager").length
                        : users.filter((u) => u.role === "cashier" || u.role === "kitchen").length}
                    </span>
                  </button>
                ))}
              </div>

              {visible.length === 0 ? (
                <p className="empty-msg">No users in this group.</p>
              ) : (
                <div className="enquiry-list">
                  {visible.map((u) => (
                    <div
                      key={u.id}
                      className={`enquiry-card${editTarget?.id === u.id ? " selected-card" : ""}`}
                      style={{ cursor: "pointer" }}
                      onClick={() => startEdit(u)}
                    >
                      <div className="enquiry-header">
                        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                          <strong>{u.username}</strong>
                          <span className={`role-badge ${ROLE_BADGE[u.role] ?? "badge-manager"}`}>
                            {ROLE_LABEL[u.role] ?? u.role}
                          </span>
                        </div>
                        <button
                          className="btn-action cancel"
                          onClick={(e) => { e.stopPropagation(); handleDelete(u); }}
                        >
                          Remove
                        </button>
                      </div>
                      <div className="enquiry-detail">
                        <span>Added by: {u.createdBy}</span>
                        <span>{new Date(u.createdAt).toLocaleDateString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* ── Right: form ── */}
            <div className="users-form-col">
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
                <h2 className="section-heading" style={{ margin: 0 }}>
                  {isEdit ? `Edit — ${editTarget?.username}` : "Add user"}
                </h2>
                {isEdit && (
                  <button className="btn-action secondary" onClick={startCreate}>
                    + New
                  </button>
                )}
              </div>

              <form className="user-form" onSubmit={handleSubmit} noValidate>

                {/* Role */}
                <div className="field-group">
                  <label className="cms-label">Role</label>
                  <div className="role-selector">
                    {["manager", "cashier", "kitchen"].map((r) => (
                      <button
                        key={r}
                        type="button"
                        className={`role-option${form.role === r ? " active" : ""}`}
                        onClick={() => setForm((f) => ({ ...f, role: r }))}
                      >
                        {ROLE_LABEL[r]}
                      </button>
                    ))}
                  </div>
                  <p className="muted" style={{ fontSize: "0.78rem", marginTop: "0.3rem" }}>
                    {form.role === "manager"
                      ? "Full admin portal access (except user management)."
                      : form.role === "cashier"
                      ? "Kiosk access — take orders, issue bills."
                      : "Kiosk access — kitchen display only."}
                  </p>
                </div>

                {/* Username (readonly on edit) */}
                {!isEdit && (
                  <div className="field-group">
                    <label className="cms-label">
                      Username
                      <input
                        data-testid="user-username"
                        className={`cms-textarea${usernameErr ? " input-error" : ""}`}
                        style={{ padding: "0.55rem 0.75rem", borderRadius: "8px", fontFamily: "inherit" }}
                        value={form.username}
                        onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
                        onBlur={() => setTouched((t) => ({ ...t, username: true }))}
                        placeholder="letters, numbers, underscores"
                        autoComplete="off"
                      />
                    </label>
                    {usernameErr && <p className="field-error">{usernameErr}</p>}
                  </div>
                )}

                {/* Password / PIN */}
                <div className="field-group">
                  <label className="cms-label">
                    {isStaffRole ? "PIN" : "Password"}
                    <input
                      data-testid="user-password"
                      type="password"
                      className={`cms-textarea${passwordErr ? " input-error" : ""}`}
                      style={{ padding: "0.55rem 0.75rem", borderRadius: "8px", fontFamily: "inherit" }}
                      value={form.password}
                      onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                      onBlur={() => setTouched((t) => ({ ...t, password: true }))}
                      placeholder={isEdit
                        ? (isStaffRole ? "4-digit PIN (leave blank to keep)" : "New password (leave blank to keep)")
                        : (isStaffRole ? "4-digit PIN" : "min 8 characters")}
                      inputMode={isStaffRole ? "numeric" : "text"}
                      maxLength={isStaffRole ? 4 : undefined}
                    />
                  </label>
                  {passwordErr && <p className="field-error">{passwordErr}</p>}
                </div>

                {serverError && <p className="error-msg">{serverError}</p>}

                <button className="btn-primary" type="submit" disabled={saving}>
                  {saving ? "Saving…" : isEdit ? "Save changes" : `Add ${ROLE_LABEL[form.role]}`}
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
