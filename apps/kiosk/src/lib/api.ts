import { getToken, clearToken } from "./auth";

const BASE = "http://localhost:8000/api/v1";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (res.status === 401 && !path.startsWith("/cafe/login")) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Session expired");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    const detail = err.detail;
    const msg = Array.isArray(detail)
      ? detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join("; ")
      : (detail ?? "Request failed");
    throw new Error(msg);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  get: <T>(path: string) => request<T>(path),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
};

export type MenuCategory = { id: string; name: string; kind: string; vegType: string | null; sortOrder: number; active: boolean };
export type MenuItem = { id: string; category_id: string; name: string; description: string | null; price: number; taxRatePercent: number; vegType: string | null; isPackaged: boolean; station: string; available: boolean; imageUrl: string | null; sortOrder: number };
export type CafeTable = { id: string; label: string; area: string | null; capacity: number; status: "free" | "occupied" | "reserved"; active: boolean; sortOrder: number };
export type MenuResponse = { categories: MenuCategory[]; items: MenuItem[] };

export type OrderItem = {
  id: string; order_id: string; menu_item_id: string;
  nameSnapshot: string; qty: number; unitPrice: number;
  taxRatePercent: number; lineSubtotal: number; lineTax: number; lineTotal: number;
  kotStatus: string | null; voided: boolean;
};
export type Order = {
  id: string; orderNo: string; orderType: string;
  table_id: string | null; status: string;
  subtotal: number; taxAmount: number; total: number;
  notes: string | null; createdAt: string; updatedAt: string;
  items: OrderItem[];
};
export type Payment = { id: string; order_id: string; mode: string; amount: number; createdAt: string };
export type Invoice = { id: string; invoiceNo: string; order_id: string; total: number; issuedAt: string };

export type KotItem = { id: string; menu_item_id: string; nameSnapshot: string; qty: number };
export type Kot = { id: string; kotNo: string; orderNo: string; station: string; status: string; createdAt: string; items: KotItem[] };
