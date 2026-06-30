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
  // 401 on a real request means the session expired — bounce to login.
  // The login endpoint itself returns 401 on bad credentials; let that surface as an error instead.
  if (res.status === 401 && !path.startsWith("/admin/login")) {
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

  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),

  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),

  // Multipart upload — let the browser set Content-Type (boundary). 401 handling mirrors request().
  upload: async <T>(path: string, file: File): Promise<T> => {
    const token = getToken();
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    });
    if (res.status === 401 && !path.startsWith("/admin/login")) {
      clearToken();
      window.location.href = "/login";
      throw new Error("Session expired");
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Upload failed" }));
      throw new Error(err.detail ?? "Upload failed");
    }
    return res.json();
  },
};

// API origin without the /api/v1 suffix — used to resolve relative /media image paths.
export const API_ORIGIN = BASE.replace(/\/api\/v1\/?$/, "");

export function resolveImg(url: string | null | undefined): string {
  if (!url) return "";
  return /^https?:\/\//.test(url) ? url : `${API_ORIGIN}${url}`;
}
