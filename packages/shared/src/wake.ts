/**
 * Coping with a sleeping API. On a free host the server (and the database behind it) goes to sleep after a quiet
 * period, and the first request afterwards can take a minute while it starts. These helpers keep the apps usable:
 *
 *  - warmUpApi: fire-and-forget request on page load, so the server is already waking while the user types.
 *  - fetchWithWake: fetch with a generous timeout; GETs (safe to repeat) are retried when the server is not
 *    answering yet. Writes are never repeated, so a booking or payment cannot be sent twice.
 *  - a small "waking up" notice shown while a request is taking unusually long.
 */

const SLOW_AFTER_MS = 4_000;
const GET_ATTEMPT_MS = 30_000;
const WRITE_ATTEMPT_MS = 60_000;
const GET_ATTEMPTS = 3;
const RETRY_STATUSES = new Set([502, 503, 504]); // what a proxy answers while the server behind it is still starting

let slowRequests = 0;
let notice: HTMLElement | null = null;

function showNotice(show: boolean) {
  if (typeof document === "undefined") return;
  if (!show) {
    notice?.remove();
    notice = null;
    return;
  }
  if (notice) return;
  notice = document.createElement("div");
  notice.setAttribute("role", "status");
  notice.setAttribute("data-testid", "api-waking");
  notice.textContent = "Waking up the server… this can take up to a minute after a quiet period.";
  Object.assign(notice.style, {
    position: "fixed", left: "50%", bottom: "16px", transform: "translateX(-50%)", zIndex: "2147483647",
    maxWidth: "calc(100vw - 32px)", padding: "10px 16px", borderRadius: "10px", font: "14px/1.4 system-ui, sans-serif",
    background: "#16181d", color: "#f7f4ea", border: "1px solid #d8b456", boxShadow: "0 4px 16px rgba(0,0,0,.4)",
    textAlign: "center",
  } as Partial<CSSStyleDeclaration>);
  document.body.appendChild(notice);
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Wake the API in the background. Not on localhost, where nothing sleeps. `apiBase` ends in /api/v1. */
export function warmUpApi(apiBase: string): void {
  if (typeof window === "undefined") return;
  if (/^(localhost|127\.0\.0\.1|\[::1\])$/.test(window.location.hostname)) return;
  try {
    // no-cors: the answer is never read, so no CORS headers are needed and nothing is logged on failure.
    void fetch(`${apiBase.replace(/\/$/, "")}/health`, { mode: "no-cors", cache: "no-store" }).catch(() => {});
  } catch {
    /* warming up is best effort */
  }
}

/** `fetch` that waits for a sleeping server. Throws the last error (an AbortError after a timeout). */
export async function fetchWithWake(url: string, init: RequestInit = {}): Promise<Response> {
  const method = (init.method ?? "GET").toUpperCase();
  const attempts = method === "GET" ? GET_ATTEMPTS : 1;
  const attemptMs = method === "GET" ? GET_ATTEMPT_MS : WRITE_ATTEMPT_MS;

  let counted = false;
  const slowTimer = setTimeout(() => {
    counted = true;
    slowRequests++;
    showNotice(true);
  }, SLOW_AFTER_MS);

  try {
    let lastError: unknown;
    for (let attempt = 1; attempt <= attempts; attempt++) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), attemptMs);
      try {
        const res = await fetch(url, { ...init, signal: controller.signal });
        if (attempt < attempts && RETRY_STATUSES.has(res.status)) {
          lastError = new Error(`HTTP ${res.status}`);
        } else {
          return res;
        }
      } catch (e) {
        lastError = e;
        if (attempt === attempts) throw e;
      } finally {
        clearTimeout(timer);
      }
      await sleep(1_500 * attempt);
    }
    throw lastError;
  } finally {
    clearTimeout(slowTimer);
    if (counted && --slowRequests <= 0) {
      slowRequests = 0;
      showNotice(false);
    }
  }
}

/** One readable sentence for a request that never got an answer (use with fetchWithWake's thrown error). */
export function networkMessage(e: unknown): string {
  if ((e as { name?: string })?.name === "AbortError") {
    return "The server took too long to answer. Please try again in a moment.";
  }
  return "Can't reach the server. Check your connection and try again.";
}
