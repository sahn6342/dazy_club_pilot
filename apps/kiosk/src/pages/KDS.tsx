import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api, Kot } from "../lib/api";
import { clearToken } from "../lib/auth";

export function KDS() {
  const [kots, setKots] = useState<Kot[]>([]);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const navigate = useNavigate();

  const load = useCallback(() => {
    api.get<Kot[]>("/cafe/kots?station=kitchen&status=pending")
      .then((data) => {
        setKots(data);
        setError("");
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load KOTs."));
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, [load]);

  async function updateStatus(kotId: string, status: "preparing" | "ready") {
    setActionError("");
    try {
      await api.patch(`/cafe/kots/${kotId}/status`, { status });
      // Remove from list if marking ready (no longer pending), or reload
      if (status === "ready") {
        setKots((prev) => prev.filter((k) => k.id !== kotId));
      } else {
        setKots((prev) =>
          prev.map((k) => k.id === kotId ? { ...k, status } : k)
        );
      }
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "Action failed.");
    }
  }

  function logout() {
    clearToken();
    navigate("/login");
  }

  return (
    <div className="kiosk-layout">
      <header className="kiosk-header">
        <span className="kiosk-logo">Dazy.club</span>
        <nav className="kiosk-nav">
          <button className="kiosk-nav-btn" onClick={() => navigate("/menu")}>Menu</button>
          <button className="kiosk-nav-btn" onClick={() => navigate("/orders")}>Orders</button>
          <button className="kiosk-nav-btn" onClick={() => navigate("/tables")}>Tables</button>
          <button className="kiosk-nav-btn active" onClick={() => navigate("/kds")}>KDS</button>
        </nav>
        <button className="kiosk-logout" onClick={logout}>Logout</button>
      </header>

      <div style={{ flex: 1, overflow: "auto" }}>
        <div style={{ padding: "1rem 1rem 0.5rem", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <h2 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--gold)" }}>
            Kitchen Display — Pending KOTs
            {kots.length > 0 && (
              <span style={{ marginLeft: "0.5rem", fontSize: "0.8rem", color: "var(--muted)", fontWeight: 400 }}>
                ({kots.length})
              </span>
            )}
          </h2>
          <button
            style={{
              background: "transparent",
              border: "1px solid var(--border)",
              borderRadius: "8px",
              color: "var(--muted)",
              fontSize: "0.82rem",
              padding: "0.3rem 0.75rem",
              cursor: "pointer",
            }}
            onClick={load}
          >
            Refresh
          </button>
        </div>

        {error && <p style={{ color: "var(--red)", padding: "1rem" }}>{error}</p>}
        {actionError && <p style={{ color: "var(--red)", padding: "0 1rem 0.5rem", fontSize: "0.85rem" }}>{actionError}</p>}

        {!error && kots.length === 0 && (
          <p style={{ color: "var(--muted)", textAlign: "center", padding: "4rem 1rem" }}>
            No pending KOTs. Kitchen is clear!
          </p>
        )}

        <div className="kds-grid">
          {kots.map((kot) => (
            <div key={kot.id} className="kot-card">
              <div className="kot-card-header">
                <span className="kot-no">KOT #{kot.kotNo}</span>
                <span className="kot-order">Order #{kot.orderNo}</span>
              </div>
              <div className="kot-items">
                {kot.items.map((item) => (
                  <div key={item.id} className="kot-item">
                    <span className="kot-item-name">{item.nameSnapshot}</span>
                    <span className="kot-item-qty">×{item.qty}</span>
                  </div>
                ))}
              </div>
              <div style={{ padding: "0 1rem 0.5rem", fontSize: "0.75rem", color: "var(--muted)" }}>
                {new Date(kot.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                {kot.status !== "pending" && (
                  <span style={{ marginLeft: "0.5rem", color: "var(--amber)", textTransform: "capitalize" }}>
                    · {kot.status}
                  </span>
                )}
              </div>
              <div className="kot-actions">
                <button
                  className="kot-btn preparing"
                  onClick={() => updateStatus(kot.id, "preparing")}
                  disabled={kot.status === "preparing"}
                >
                  {kot.status === "preparing" ? "Preparing…" : "Mark Preparing"}
                </button>
                <button
                  className="kot-btn ready"
                  onClick={() => updateStatus(kot.id, "ready")}
                >
                  Mark Ready
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
