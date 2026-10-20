// Cloudflare Worker that drives the API's scheduler. Every cron tick it:
//   1. POSTs /api/v1/internal/sweep   -> expires stale pending bookings, reconciles missed payments
//   2. GETs  /api/v1/health/ready     -> fails loudly if the database or schema is unhealthy
// A non-2xx answer or a timeout makes the invocation FAIL, which Cloudflare records (Workers > Logs / alerts).
// Config: API_BASE (var), INTERNAL_TOKEN (secret) must equal DAZY_INTERNAL_TOKEN on the API.

const TIMEOUT_MS = 20_000;

function requireConfig(env) {
  if (!env.API_BASE) throw new Error("API_BASE is not set (wrangler.toml [vars])");
  if (!env.INTERNAL_TOKEN) throw new Error("INTERNAL_TOKEN is not set (wrangler secret put INTERNAL_TOKEN)");
  return env.API_BASE.replace(/\/+$/, "") + "/api/v1";
}

export async function runSweep(env, fetchImpl = fetch) {
  const base = requireConfig(env);
  const requestId = `cron-${crypto.randomUUID()}`; // shows up in the API's access log and Sentry tags

  const sweep = await fetchImpl(`${base}/internal/sweep`, {
    method: "POST",
    headers: { "X-Internal-Token": env.INTERNAL_TOKEN, "X-Request-ID": requestId },
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  const sweepBody = await sweep.text();
  if (!sweep.ok) {
    throw new Error(`sweep failed: HTTP ${sweep.status} ${sweepBody.slice(0, 200)} (request ${requestId})`);
  }

  const ready = await fetchImpl(`${base}/health/ready`, {
    headers: { "X-Request-ID": requestId },
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!ready.ok) {
    const detail = (await ready.text()).slice(0, 300);
    throw new Error(`API not ready: HTTP ${ready.status} ${detail} (request ${requestId})`);
  }
  return { requestId, ...JSON.parse(sweepBody) };
}

export default {
  async scheduled(_event, env) {
    try {
      const result = await runSweep(env);
      console.log(JSON.stringify({ msg: "sweep ok", ...result }));
    } catch (err) {
      console.error(JSON.stringify({ msg: "sweep failed", error: String(err && err.message ? err.message : err) }));
      throw err; // mark the invocation as failed
    }
  },

  // Nothing is exposed over HTTP: the worker only runs on its cron trigger.
  async fetch() {
    return new Response("Not found", { status: 404 });
  },
};
