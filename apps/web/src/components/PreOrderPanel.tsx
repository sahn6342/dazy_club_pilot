import { useEffect, useState } from "react";
import { getPublicMenu, createPreorder, type PublicMenu, type PreOrderResult } from "../lib/api";

interface PreOrderPanelProps {
  bookingRef: string;
  contact: string;
}

export function PreOrderPanel({ bookingRef, contact }: PreOrderPanelProps) {
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState<PublicMenu | null>(null);
  const [loadError, setLoadError] = useState("");
  const [cart, setCart] = useState<Record<string, number>>({});
  const [status, setStatus] = useState<"idle" | "submitting" | "done" | "error">("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState<PreOrderResult | null>(null);

  useEffect(() => {
    if (!open || menu) return;
    getPublicMenu().then(setMenu).catch((err) => setLoadError(err?.message ?? "Could not load the menu."));
  }, [open, menu]);

  function adjustQty(id: string, delta: number) {
    setCart((c) => {
      const next = { ...c };
      const updated = (next[id] ?? 0) + delta;
      if (updated <= 0) delete next[id];
      else next[id] = updated;
      return next;
    });
  }

  const cartEntries = Object.entries(cart);
  const total = menu
    ? cartEntries.reduce((sum, [id, qty]) => sum + (menu.items.find((i) => i.id === id)?.price ?? 0) * qty, 0)
    : 0;

  async function submit() {
    if (!cartEntries.length) return;
    setStatus("submitting");
    setError("");
    try {
      const res = await createPreorder(
        bookingRef,
        contact,
        cartEntries.map(([menu_item_id, qty]) => ({ menu_item_id, qty }))
      );
      setResult(res);
      setStatus("done");
    } catch (err: any) {
      setStatus("error");
      setError(err?.message ?? "Could not place your pre-order. Please try again.");
    }
  }

  if (!open) {
    return (
      <button type="button" className="button secondary" onClick={() => setOpen(true)}>
        Add food &amp; drinks for your visit
      </button>
    );
  }

  if (status === "done" && result) {
    return (
      <div className="preorder-panel" data-testid="preorder-done">
        <p className="eyebrow">Pre-order placed</p>
        <p>
          Order <strong>{result.orderNo}</strong> will be ready at the counter — total{" "}
          <strong>₹{result.total.toFixed(2)}</strong>.
        </p>
      </div>
    );
  }

  return (
    <div className="preorder-panel">
      <p className="eyebrow">Add food &amp; drinks</p>
      {loadError && <p className="form-message error">{loadError}</p>}
      {!menu && !loadError && <p className="muted">Loading menu…</p>}
      {menu && (
        <>
          <div className="preorder-items">
            {menu.items.filter((i) => i.available).map((item) => (
              <div className="preorder-item" key={item.id}>
                <span className="preorder-item-name">{item.name}</span>
                <span className="preorder-item-price">₹{item.price}</span>
                <div className="preorder-qty">
                  <button type="button" onClick={() => adjustQty(item.id, -1)} disabled={!cart[item.id]}>
                    −
                  </button>
                  <span data-testid={`qty-${item.id}`}>{cart[item.id] ?? 0}</span>
                  <button type="button" onClick={() => adjustQty(item.id, 1)}>
                    +
                  </button>
                </div>
              </div>
            ))}
          </div>
          <p className="summary-total" data-testid="preorder-total">Total: ₹{total.toFixed(2)}</p>
          {status === "error" && <p className="form-message error">{error}</p>}
          <button
            type="button"
            className="button primary"
            disabled={!cartEntries.length || status === "submitting"}
            onClick={submit}
          >
            {status === "submitting" ? "Placing order…" : "Place pre-order"}
          </button>
        </>
      )}
    </div>
  );
}
