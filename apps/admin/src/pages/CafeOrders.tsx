import { useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { api } from "../lib/api";

type OrderItem = {
  id: string; order_id: string; menu_item_id: string;
  nameSnapshot: string; qty: number; unitPrice: number;
  taxRatePercent: number; lineSubtotal: number; lineTax: number; lineTotal: number;
  kotStatus: string | null; voided: boolean;
};
type Payment = { id: string; order_id: string; mode: string; amount: number; createdAt: string };
type Order = {
  id: string; orderNo: string; orderType: string;
  table_id: string | null; status: string;
  subtotal: number; taxAmount: number; total: number;
  notes: string | null; createdAt: string; updatedAt: string;
  items: OrderItem[];
};
type OrderDetail = Order & { payments?: Payment[] };

type StatusFilter = "all" | "open" | "paid" | "cancelled";

const STATUS_BADGE: Record<string, { label: string; color: string; bg: string }> = {
  open:        { label: "Open",        color: "#ffb74d", bg: "rgba(255,183,77,0.15)" },
  in_kitchen:  { label: "In Kitchen",  color: "#42a5f5", bg: "rgba(66,165,245,0.15)" },
  paid:        { label: "Paid",        color: "#4caf50", bg: "rgba(76,175,80,0.15)" },
  cancelled:   { label: "Cancelled",   color: "#8a8d96", bg: "rgba(138,141,150,0.1)" },
};

function statusBadge(status: string) {
  const s = STATUS_BADGE[status] ?? { label: status, color: "#8a8d96", bg: "rgba(138,141,150,0.1)" };
  return (
    <span style={{
      display: "inline-block",
      background: s.bg,
      color: s.color,
      border: `1px solid ${s.color}`,
      borderRadius: "6px",
      padding: "0.15rem 0.55rem",
      fontSize: "0.75rem",
      fontWeight: 700,
      textTransform: "capitalize",
    }}>
      {s.label}
    </span>
  );
}

export function CafeOrders() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, OrderDetail>>({});
  const [detailLoading, setDetailLoading] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api.get<Order[]>("/cafe/orders")
      .then((data) => { setOrders(data); setError(""); })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load orders."))
      .finally(() => setLoading(false));
  }, []);

  async function toggleExpand(id: string) {
    if (expanded === id) { setExpanded(null); return; }
    setExpanded(id);
    if (detail[id]) return;
    setDetailLoading(id);
    try {
      const d = await api.get<OrderDetail>(`/cafe/orders/${id}`);
      setDetail((prev) => ({ ...prev, [id]: d }));
    } catch {
      // silently fail; will show no detail
    } finally {
      setDetailLoading(null);
    }
  }

  const filtered = orders.filter((o) => {
    if (filter === "all") return true;
    if (filter === "open") return o.status === "open" || o.status === "in_kitchen";
    if (filter === "paid") return o.status === "paid";
    if (filter === "cancelled") return o.status === "cancelled";
    return true;
  });

  const TABS: { key: StatusFilter; label: string }[] = [
    { key: "all", label: `All (${orders.length})` },
    { key: "open", label: `Open (${orders.filter((o) => o.status === "open" || o.status === "in_kitchen").length})` },
    { key: "paid", label: `Paid (${orders.filter((o) => o.status === "paid").length})` },
    { key: "cancelled", label: `Cancelled (${orders.filter((o) => o.status === "cancelled").length})` },
  ];

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Café Orders" />
        <div className="page-body">

          {/* Filter tabs */}
          <div className="tab-pills" style={{ marginBottom: "1.25rem" }}>
            {TABS.map((t) => (
              <button
                key={t.key}
                className={`court-pill${filter === t.key ? " active" : ""}`}
                onClick={() => setFilter(t.key)}
              >
                {t.label}
              </button>
            ))}
          </div>

          {error && <p className="error-msg">{error}</p>}
          {loading && <p className="empty-msg">Loading orders…</p>}

          {!loading && !error && filtered.length === 0 && (
            <p className="empty-msg">No orders in this category.</p>
          )}

          {!loading && !error && filtered.length > 0 && (
            <div className="enquiry-list">
              {filtered.map((order) => {
                const isExpanded = expanded === order.id;
                const d = detail[order.id];
                const isLoadingDetail = detailLoading === order.id;

                return (
                  <div key={order.id} className="enquiry-card" style={{ cursor: "pointer" }} onClick={() => toggleExpand(order.id)}>
                    {/* Row summary */}
                    <div className="enquiry-header" style={{ alignItems: "flex-start" }}>
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                          <strong style={{ fontSize: "0.95rem" }}>#{order.orderNo}</strong>
                          {statusBadge(order.status)}
                          <span style={{ fontSize: "0.8rem", color: "var(--muted)", textTransform: "capitalize" }}>
                            {order.orderType}
                          </span>
                        </div>
                        <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>
                          {new Date(order.createdAt).toLocaleString()} · {order.items.length} item{order.items.length !== 1 ? "s" : ""}
                        </div>
                      </div>
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "0.2rem", flexShrink: 0 }}>
                        <span style={{ fontSize: "1rem", fontWeight: 700, color: "var(--gold)" }}>
                          ₹{Number(order.total).toFixed(2)}
                        </span>
                        <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
                          {isExpanded ? "▲ Collapse" : "▼ Details"}
                        </span>
                      </div>
                    </div>

                    {/* Expanded detail */}
                    {isExpanded && (
                      <div style={{ marginTop: "0.75rem", borderTop: "1px solid var(--border)", paddingTop: "0.75rem" }} onClick={(e) => e.stopPropagation()}>
                        {isLoadingDetail && <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>Loading…</p>}
                        {d && (
                          <>
                            {/* Items */}
                            <div style={{ marginBottom: "0.75rem" }}>
                              <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--muted)", marginBottom: "0.4rem", textTransform: "uppercase", letterSpacing: "0.06em" }}>Items</div>
                              <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
                                {d.items.map((item) => (
                                  <div key={item.id} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.87rem" }}>
                                    <span style={{ color: item.voided ? "var(--muted)" : "var(--text)", textDecoration: item.voided ? "line-through" : "none" }}>
                                      {item.nameSnapshot}
                                      {item.voided && " (voided)"}
                                    </span>
                                    <span style={{ color: "var(--muted)" }}>
                                      ×{item.qty} · ₹{Number(item.lineTotal).toFixed(2)}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>

                            {/* Totals */}
                            <div style={{ display: "flex", gap: "1.5rem", fontSize: "0.82rem", color: "var(--muted)", marginBottom: "0.75rem" }}>
                              <span>Subtotal ₹{Number(d.subtotal).toFixed(2)}</span>
                              <span>Tax ₹{Number(d.taxAmount).toFixed(2)}</span>
                              <span style={{ color: "var(--gold)", fontWeight: 700 }}>Total ₹{Number(d.total).toFixed(2)}</span>
                            </div>

                            {/* Payments */}
                            {d.payments && d.payments.length > 0 && (
                              <div>
                                <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--muted)", marginBottom: "0.4rem", textTransform: "uppercase", letterSpacing: "0.06em" }}>Payments</div>
                                {d.payments.map((p) => (
                                  <div key={p.id} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.87rem", color: "var(--text)" }}>
                                    <span style={{ textTransform: "uppercase", fontSize: "0.78rem", color: "var(--green)", fontWeight: 600 }}>{p.mode}</span>
                                    <span>₹{Number(p.amount).toFixed(2)}</span>
                                  </div>
                                ))}
                              </div>
                            )}

                            {order.notes && (
                              <div style={{ marginTop: "0.5rem", fontSize: "0.82rem", color: "var(--muted)" }}>
                                Note: {order.notes}
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
