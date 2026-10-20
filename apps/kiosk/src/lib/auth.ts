// Sessions live in an httpOnly cookie set by the API (JavaScript cannot read it, so an injected
// script cannot steal it). This module only keeps a UI hint so the router knows whether to show
// the login page; the API is the real gate and answers 401 once the cookie is gone or revoked.
const BASE = (import.meta as any).env?.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

// Optional bearer token: never written by the app any more. Only a token injected by a script or
// test (for example Playwright) lands here, and the API still accepts it.
const TOKEN_KEY = "dazy_kiosk_token";
const SESSION_KEY = "dazy_kiosk_session";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

/** Call after a successful login: remember (as a hint only) that a session cookie exists. */
export function markSignedIn(): void {
  localStorage.setItem(SESSION_KEY, "1");
}

/** End the session: forget the hint and ask the API to revoke the token and clear the cookie. */
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(SESSION_KEY);
  // Best effort; a failure here only means the cookie lives until it expires or the next 401.
  fetch(`${BASE}/cafe/logout`, {
    method: "POST",
    credentials: "include",
    headers: { "X-Requested-With": "dazy" },
  }).catch(() => undefined);
}

export function isAuthenticated(): boolean {
  return !!localStorage.getItem(SESSION_KEY) || !!getToken();
}
