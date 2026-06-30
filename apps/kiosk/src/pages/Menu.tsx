import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, MenuCategory, MenuItem, MenuResponse, Order } from "../lib/api";
import { clearToken } from "../lib/auth";
import { PaymentModal } from "../components/PaymentModal";

const VEG_ICON: Record<string, string> = { veg: "🟢", nonveg: "🔴", egg: "🟡" };

type Cart = Record<string, number>; // item_id → qty

// ─── Menu ─────────────────────────────────────────────────────────────────────

export function Menu() {
  const [data, setData] = useState<MenuResponse | null>(null);
  const [activeCat, setActiveCat] = useState<string>("all");
  const [cart, setCart] = useState<Cart>({});
  const [error, setError] = useState("");
  const [orderError, setOrderError] = useState("");
  const [placing, setPlacing] = useState(false);
  const [activeOrder, setActiveOrder] = useState<Order | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.get<MenuResponse>("/cafe/menu")
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load menu."));
  }, []);

  function logout() {
    clearToken();
    navigate("/login");
  }

  function addToCart(id: string) {
    setCart((c) => ({ ...c, [id]: (c[id] ?? 0) + 1 }));
  }

  function removeFromCart(id: string) {
    setCart((c) => {
      const next = { ...c };
      if ((next[id] ?? 0) <= 1) delete next[id];
      else next[id]--;
      return next;
    });
  }

  function clearCart() {
    setCart({});
  }

  const categories: MenuCategory[] = data?.categories ?? [];
  const items: MenuItem[] = data?.items ?? [];
  const filtered = activeCat === "all" ? items : items.filter((i) => i.category_id === activeCat);

  // Cart calculations
  const itemMap = Object.fromEntries(items.map((i) => [i.id, i]));
  const cartEntries = Object.entries(cart).filter(([id]) => itemMap[id]);
  const totalQty = cartEntries.reduce((s, [, q]) => s + q, 0);

  const lineSubtotals = cartEntries.map(([id, qty]) => {
    const item = itemMap[id];
    const price = item.price;
    const taxRate = item.taxRatePercent / 100;
    const subtotal = price * qty;
    return { id, item, qty, subtotal, tax: subtotal * taxRate };
  });

  const grandSubtotal = lineSubtotals.reduce((s, l) => s + l.subtotal, 0);
  const grandTax = lineSubtotals.reduce((s, l) => s + l.tax, 0);
  const grandTotal = grandSubtotal + grandTax;

  async function placeOrder() {
    if (cartEntries.length === 0) return;
    setPlacing(true);
    setOrderError("");
    try {
      const orderItems = cartEntries.map(([menu_item_id, qty]) => ({ menu_item_id, qty }));
      const order = await api.post<Order>("/cafe/orders", {
        orderType: "quick",
        items: orderItems,
      });
      setActiveOrder(order);
    } catch (e: unknown) {
      setOrderError(e instanceof Error ? e.message : "Failed to place order.");
    } finally {
      setPlacing(false);
    }
  }

  function handlePaymentComplete() {
    clearCart();
    setActiveOrder(null);
    setOrderError("");
  }

  return (
    <div className="kiosk-layout">
      <header className="kiosk-header">
        <span className="kiosk-logo">Dazy.club</span>
        <nav className="kiosk-nav">
          <button className="kiosk-nav-btn active" onClick={() => navigate("/menu")}>Menu</button>
          <button className="kiosk-nav-btn" onClick={() => navigate("/orders")}>Orders</button>
          <button className="kiosk-nav-btn" onClick={() => navigate("/tables")}>Tables</button>
          <button className="kiosk-nav-btn" onClick={() => navigate("/kds")}>KDS</button>
        </nav>
        <button className="kiosk-logout" onClick={logout}>Logout</button>
      </header>

      <div className="kiosk-body">
        <aside className="category-rail">
          <button
            className={`cat-btn${activeCat === "all" ? " active" : ""}`}
            onClick={() => setActiveCat("all")}
          >
            All
          </button>
          {categories.map((c) => (
            <button
              key={c.id}
              className={`cat-btn${activeCat === c.id ? " active" : ""}`}
              onClick={() => setActiveCat(c.id)}
            >
              {c.name}
            </button>
          ))}
        </aside>

        <main className="item-grid">
          {error && <p className="kiosk-error">{error}</p>}
          {!error && filtered.length === 0 && (
            <p className="kiosk-empty">No items in this category.</p>
          )}
          {filtered.map((item) => {
            const qty = cart[item.id] ?? 0;
            return (
              <div key={item.id} className={`item-card${qty > 0 ? " in-cart" : ""}`}>
                {item.imageUrl && (
                  <img src={item.imageUrl} alt={item.name} className="item-img" />
                )}
                <div className="item-info">
                  <span className="item-veg">{item.vegType ? VEG_ICON[item.vegType] ?? "" : ""}</span>
                  <span className="item-name">{item.name}</span>
                  {item.description && <p className="item-desc">{item.description}</p>}
                  <span className="item-price">₹{Number(item.price).toFixed(0)}</span>
                </div>
                {qty === 0 ? (
                  <button className="item-add" onClick={() => addToCart(item.id)}>+ Add</button>
                ) : (
                  <div className="item-qty-row">
                    <button className="qty-btn" onClick={() => removeFromCart(item.id)}>−</button>
                    <span className="qty-count">{qty}</span>
                    <button className="qty-btn" onClick={() => addToCart(item.id)}>+</button>
                  </div>
                )}
              </div>
            );
          })}
        </main>

        {/* Cart panel */}
        <aside className={`cart-panel${totalQty > 0 ? " has-items" : ""}`}>
          <div className="cart-header">
            <span className="cart-title">{totalQty > 0 ? `Order (${totalQty})` : "Order"}</span>
            {totalQty > 0 && (
              <button className="cart-clear" onClick={clearCart}>Clear</button>
            )}
          </div>

          {totalQty === 0 ? (
            <p className="cart-empty">Add items to start an order.</p>
          ) : (
            <>
              <div className="cart-lines">
                {lineSubtotals.map(({ id, item, qty, subtotal }) => (
                  <div key={id} className="cart-line">
                    <div className="cart-line-name">{item.name}</div>
                    <div className="cart-line-right">
                      <div className="cart-line-qty-ctrl">
                        <button className="qty-btn sm" onClick={() => removeFromCart(id)}>−</button>
                        <span>{qty}</span>
                        <button className="qty-btn sm" onClick={() => addToCart(id)}>+</button>
                      </div>
                      <span className="cart-line-amt">₹{subtotal.toFixed(2)}</span>
                    </div>
                  </div>
                ))}
              </div>

              <div className="cart-totals">
                <div className="cart-row">
                  <span>Subtotal</span>
                  <span>₹{grandSubtotal.toFixed(2)}</span>
                </div>
                <div className="cart-row muted">
                  <span>Tax</span>
                  <span>₹{grandTax.toFixed(2)}</span>
                </div>
                <div className="cart-row total">
                  <span>Total</span>
                  <span>₹{grandTotal.toFixed(2)}</span>
                </div>
              </div>

              {orderError && (
                <p style={{ color: "var(--red)", fontSize: "0.82rem", padding: "0 0.75rem", marginBottom: "0.25rem" }}>
                  {orderError}
                </p>
              )}

              <button
                className="cart-order-btn"
                onClick={placeOrder}
                disabled={placing}
              >
                {placing ? "Placing…" : `Place Order · ₹${grandTotal.toFixed(2)}`}
              </button>
            </>
          )}
        </aside>
      </div>

      {/* Payment modal */}
      {activeOrder && (
        <PaymentModal
          order={activeOrder}
          onClose={() => setActiveOrder(null)}
          onComplete={handlePaymentComplete}
        />
      )}
    </div>
  );
}
