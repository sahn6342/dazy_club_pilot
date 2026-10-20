# Cron worker

Cloudflare Worker that makes the API's scheduled jobs actually run. Every 5 minutes it:

1. `POST /api/v1/internal/sweep` with the `X-Internal-Token` header: expires stale pending bookings and
   reconciles payments whose webhook never arrived;
2. `GET /api/v1/health/ready`: fails the run if the database or the schema is unhealthy.

A non-2xx answer or a 20 s timeout **fails the invocation**, which shows up in Cloudflare (Workers > dazy-club-sweep >
Logs, and you can attach a notification to failed cron runs). Each run sends an `X-Request-ID: cron-<uuid>` that appears
in the API's access log and on any Sentry error it causes. Nothing is served over HTTP (`fetch` answers 404).

## Deploy (one time)

```bash
cd infra/cron-worker
# 1. API side: set DAZY_INTERNAL_TOKEN on Render to a random 32+ character string (the endpoint is a 404 until you do)
# 2. Worker side:
npx wrangler login
npx wrangler secret put INTERNAL_TOKEN       # paste the SAME value
npx wrangler deploy
```

Edit `API_BASE` in `wrangler.toml` first if the API is not at `https://api.dazyclub.com`.

## Neon cost note

A query every 5 minutes stops Neon from ever suspending its compute, which uses your compute-hours around the clock.
To let it sleep overnight, restrict the hours in `wrangler.toml` (cron runs in UTC), e.g. `"*/5 0-16 * * *"` for
05:30-22:30 IST. Pending bookings are also expired lazily whenever someone loads the slot grid, so a quiet night is safe.

## Test

```bash
cd infra/cron-worker && npm test      # node:test, no dependencies
```

(The backend test suite runs these too.) Not yet exercised against a deployed Worker: after the first deploy, trigger it
once from the Cloudflare dashboard (Triggers > Cron > Test) and check the API's logs for the `cron-` request id.
