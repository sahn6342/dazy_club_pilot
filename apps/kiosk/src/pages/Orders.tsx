import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Order } from "../lib/api";
import { clearToken } from "../lib/auth";
import { PaymentModal } from "../components/PaymentModal";

type Tab = "open" | "history";

const OPEN_STATUSES = new Set(["open", "in_kitchen", "served"]);

const STATUS_COLOR: Record<string, { color: string; label: string }> = {
  open:       { color: "var(--amber)",  label: "Open" },
  in_kitchen: { color: "#42a5f5",       label: "In Kitchen" },
  served:     { color: "var(--green)",  label: "Served" },
  paid:       { color: "var(--green)",  label: "Paid" },
  cancelled:  { color: "var(--muted)", label: "Cancelled" },
  void:       { color: "var(--muted)", label: "Void" },
};

function StatusBadge({ status }: { status: string }) {
  const s = STATUS_COLOR[status] ?? { color: "var(--muted)", label: status };
  return (
    <span style={{
      fontSize: "0.72rem", fontWeight: 700, padding: "0.15rem 0.5rem",
      borderRadius: "5px", border: `1px solid ${s.color}`,
      color: s.color, background: `${s.color}18`,
      textTransform: "uppercase", letterSpacing: "0.04em",
    }}>
      {s.label}
    </span>
  );
}

export function Orders() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [tab, setTab] = useState<Tab>("open");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [payOrder, setPayOrder] = useState<Order | null>(null);
  const navigate = useNavigate();

  const load = useCallback(() => {
    api.get<Order[]>("/cafe/orders")
      .then((data) => { setOrders(data); setError(""); })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load orders."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 15_000);
    return () => clearInterval(iv);
  }, [load]);

  function logout() { clearToken(); navigate("/login"); }

  const openOrders = orders.filter((o) => OPEN_STATUSES.has(o.status));
  const historyOrders = orders.filter((o) => !OPEN_STATUSES.has(o.status));
  const shown = tab === "open" ? openOrders : historyOrders;

  function fmt(iso: string) {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) +
      " · " + d.toLocaleDateString([], { day: "numeric", month: "short" });
  }

  return (
    <div className="kiosk-layout">
      <header className="kiosk-header">
        <span className="kiosk-logo">Dazy.club</span>
        <nav className="kiosk-nav">
          <button className="kiosk-nav-btn" onClick={() => navigate("/menu")}>Menu</button>
          <button className="kiosk-nav-btn active" onClick={() => navigate("/orders")}>Orders</button>
          <button className="kiosk-nav-btn" onClick={() => navigate("/tables")}>Tables</button>
          <button className="kiosk-nav-btn" onClick={() => navigate("/kds")}>KDS</button>
        </nav>
        <button className="kiosk-logout" onClick={logout}>Logout</button>
      </header>

      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Tabs */}
        <div style={{ display: "flex", gap: "0.5rem", padding: "0.9rem 1rem 0", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
          <button
            onClick={() => setTab("open")}
            style={{
              background: tab === "open" ? "var(--gold-dim)" : "transparent",
              border: "none", borderBottom: tab === "open" ? "2px solid var(--gold)" : "2px solid transparent",
              color: tab === "open" ? "var(--gold)" : "var(--muted)",
              fontWeight: 700, fontSize: "0.9rem", padding: "0.4rem 1rem",
              cursor: "pointer", borderRadius: "4px 4px 0 0",
            }}
          >
            Open ({openOrders.length})
          </button>
          <button
            onClick={() => setTab("history")}
            style={{
              background: tab === "history" ? "var(--gold-dim)" : "transparent",
              border: "none", borderBottom: tab === "history" ? "2px solid var(--gold)" : "2px solid transparent",
              color: tab === "history" ? "var(--gold)" : "var(--muted)",
              fontWeight: 700, fontSize: "0.9rem", padding: "0.4rem 1rem",
              cursor: "pointer", borderRadius: "4px 4px 0 0",
            }}
          >
            History ({historyOrders.length})
          </button>
          <button
            onClick={load}
            style={{ marginLeft: "auto", background: "transparent", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--muted)", fontSize: "0.8rem", padding: "0.25rem 0.75rem", cursor: "pointer", marginBottom: "4px" }}
          >
            ↻ Refresh
          </button>
        </div>

        {/* List */}
        <div style={{ flex: 1, overflowY: "auto", padding: "0.75rem 1rem" }}>
          {loading && <p className="kiosk-empty">Loading orders…</p>}
          {error && <p className="kiosk-error">{error}</p>}

          {!loading && !error && shown.length === 0 && (
            <p className="kiosk-empty">
              {tab === "open" ? "No open orders." : "No order history."}
            </p>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
            {shown.map((order) => (
              <div
                key={order.id}
                style={{
                  background: "var(--surface)", border: "1px solid var(--border)",
                  borderRadius: "var(--radius)", padding: "0.85rem 1rem",
                  display: "flex", alignItems: "center", gap: "1rem",
                }}
              >
                {/* Left: order info */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.3rem" }}>
                    <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>#{order.orderNo}</span>
                    <StatusBadge status={order.status} />
                    <span style={{ fontSize: "0.78rem", color: "var(--muted)", textTransform: "capitalize" }}>
                      {order.orderType.replace("_", " ")}
                    </span>
                    {order.booking_id && (
                      <span style={{
                        fontSize: "0.72rem", fontWeight: 700, padding: "0.15rem 0.5rem",
                        borderRadius: "5px", border: "1px solid var(--gold)",
                        color: "var(--gold)", background: "var(--gold-dim)",
                      }}>
                        🎫 Pre-order
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>
                    {order.items.length} item{order.items.length !== 1 ? "s" : ""} · {fmt(order.createdAt)}
                  </div>
                  {order.items.length > 0 && (
                    <div style={{ fontSize: "0.78rem", color: "var(--muted)", marginTop: "0.2rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {order.items.filter((i) => !i.voided).map((i) => `${i.nameSnapshot} ×${i.qty}`).join(", ")}
                    </div>
                  )}
                </div>

                {/* Right: total + action */}
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "0.5rem", flexShrink: 0 }}>
                  <span style={{ fontWeight: 800, fontSize: "1.05rem", color: "var(--gold)" }}>
                    ₹{Number(order.total).toFixed(2)}
                  </span>
                  {OPEN_STATUSES.has(order.status) && order.status !== "paid" && order.total > 0 && order.items.length > 0 && (
                    <button
                      className="cart-order-btn"
                      style={{ margin: 0, padding: "0.45rem 1.1rem", fontSize: "0.85rem" }}
                      onClick={() => setPayOrder(order)}
                    >
                      Pay
                    </button>
                  )}
                  {order.status === "paid" && (
                    <span style={{ fontSize: "0.78rem", color: "var(--green)" }}>✓ Settled</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {payOrder && (
        <PaymentModal
          order={payOrder}
          onClose={() => setPayOrder(null)}
          onComplete={() => { setPayOrder(null); load(); }}
        />
      )}
    </div>
  );
}
