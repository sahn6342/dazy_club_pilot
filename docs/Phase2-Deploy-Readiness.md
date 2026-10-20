# Phase 2 — deploy-readiness review

Written 2026-10-20 after Phase 0, Phase 1 and Phase 2 (workstreams A–H) were committed locally (`d5b0437` … `e0fafba`). Nothing has been pushed or deployed. This is a candid list of what is proven, what is not, and the order to do things in. Companion docs: [App-Overview.md](App-Overview.md) (how it works), [Phase2-Plan.md](Phase2-Plan.md) (what was planned).

## 1. Read this before you push

**`git push origin main` is a production deploy.** `render.yaml` has `autoDeployTrigger: commit` on `main`, so Render builds and starts the new API as soon as the push lands. `.github/workflows/deploy.yml` also fires on every push to `main` (tests, then an SSH deploy of the *self-host* stack if the `DEPLOY_*` secrets exist). Do the checklist in section 5 first, ideally against a staging Render service on its own Neon branch, and push `main` last.

What the push would do on Render, in order: the API starts, `config_guard` checks the environment **before touching the database** and refuses to boot if production settings are missing (a failed new deploy leaves the previous deploy serving), then it runs the 9 new migrations (`h1i2j3k4l5m6` … `p9q0r1s2t3u4`, assuming production is at `g0h1i2j3k4l5`: check `SELECT version_num FROM alembic_version`) on Neon, then seeds. Postgres DDL is transactional, so a migration that fails rolls back; migrations that already completed stay applied.

## 2. What is verified, and how

| Area | Evidence | Limits |
|---|---|---|
| Backend behaviour | 752 pytest tests pass (1 skipped: the Postgres migration test) | **SQLite only**, **Windows only**. Never run on Linux/CI or Postgres |
| Frontends | `tsc` clean on web, admin, kiosk; Playwright specs for booking, payments (noop), sessions, audit, refunds, delete/export, notifications, kiosk | Admin `courts`/`schedule`, web `gallery` and the kiosk-tables screenshot specs fail for reasons unrelated to this work (stale specs / shared dev state); E2E is not in CI |
| Cron worker | 9 `node:test` tests | Not deployed; never run on Cloudflare |
| Money and booking safety | Concurrency-safe refund reservation, late-payment refund, amount-mismatch flag, atomic multi-slot create, reconciliation, all tested with fakes | Razorpay itself was never called: tests use the `noop` provider and fake responses |

## 3. Unverified items (need your accounts, credentials or a Postgres)

Each is built and unit-tested against mocks, and is **not proven against the real service**. Order = how likely it is to bite on day one.

1. **Cookie sessions on your real domains.** Tested on `localhost` only. If an SPA and the API are on different *sites* (for example `admin-xyz.pages.dev` calling `api.dazyclub.com`), SameSite=Lax cookies are not sent: staff would appear signed in (a local UI hint) while every API call returns 401 and bounces them to login. Fix is either one parent domain for everything or `DAZY_COOKIE_SAMESITE=none` (forces Secure).
2. **Foreign-key migration on Postgres.** Verified on SQLite with seeded dirty data (repair, indexes, downgrade). The same scenario exists for Postgres (`DAZY_TEST_PG_URL`, throwaway DB whose name contains `test`) but has **not been run**: I had no credentials, and Docker was not running.
3. **Razorpay live path.** Test-mode checkout, webhook signature and `payment.captured` handling, partial and full refunds, late-payment auto-refund, and reconciliation all rely on request/response shapes written from the docs. The webhook must be registered in the Razorpay dashboard.
4. **Turnstile.** Verified with a stubbed verifier. The widget's allowed-hostname list in the Cloudflare dashboard must include every site that hosts the web build, or every booking, enquiry and OTP request is rejected.
5. **R2 uploads.** Tested against an in-memory S3 fake. Real bucket permissions, the public URL and caching are unproven.
6. **Email.** SMTP adapter and failure classification are tested; no message has ever been delivered, and sender-domain setup (SPF/DKIM) is untested. Without `DAZY_NOTIFY_PROVIDER=email` + `SMTP_*`, production customers receive **no email**: the API only logs a warning.
7. **WhatsApp (Meta Cloud API) and SMS (MSG91).** Adapters tested against mocked HTTP. Meta template approval and DLT registration take days; until then those messages are *skipped* (visible in Admin → Notifications), and phone-only customers receive nothing, **including OTP codes**, so contact-only booking search is unusable for them (ref + contact lookup still works).
8. **Sentry** (only an in-memory transport), **the Cloudflare cron worker**, **the uptime monitor**: none exist in the real world yet.
9. **Behaviour under Postgres concurrency.** The double-booking guard (partial unique index), the DB-backed rate limiter and the refund reservation use plain SQL that behaves the same on Postgres, but every test ran on SQLite.

## 4. Open risks and known gaps

**Operational**
- **Proxy hops must be right.** Rate limits key on the client IP found `DAZY_PROXY_HOPS` entries from the right of `X-Forwarded-For`. Too high a number falls back to the proxy's address, so *all* visitors share one limit and start getting 429s; too low keys on a Cloudflare edge address. Render alone = 1; put Cloudflare in front of the API and it is 2. Verify with a real request (step 12).
- **The scheduler is a separate deployable.** Without the cron worker, booking expiry only happens when someone loads the slot grid, payment reconciliation never runs, and notification retries never fire. `/health/ready` shows `sweep.lastRunAt`, but nothing alerts on it until you set up the monitor and a failure alert on the worker.
- **Neon compute hours.** A request every 5 minutes (cron or uptime monitor) means Neon never suspends. Restrict the cron hours if you are on a plan with limited compute-hours (see `infra/cron-worker/README.md`).
- **Render free plan** spins down when idle; with the cron worker running every 5 minutes it stays awake in practice, but cold starts after a deploy are still slow and webhooks can arrive while it wakes (Razorpay retries; reconciliation backstops).
- **Single instance assumed** for the sweep heartbeat shown on `/health/ready` (in memory). Rate limits, OTP and revocation are in the database and are safe across instances.
- **Backups and rollback are untested.** All Phase 2 migrations are additive, except `courts.capacity` is forced to 1 and foreign keys are added, so redeploying the previous code is *probably* safe, but I have not tried it. The reliable rollback is a Neon restore to a point before the deploy: take a branch/backup first and check your plan's restore window.

**Product / security**
- **Kiosk PINs are 4 digits.** Per-username lockout (5 failures / 15 min) makes that acceptable, but a longer PIN is stronger.
- **OTP delivery failures are silent to the customer** (by design: the response must not reveal whether a contact has bookings). Watch failed `otp` rows in the notification log.
- **CSP is report-only.** It hard-codes `https://api.dazyclub.com` as the API origin in each `public/_headers` (and `Caddyfile` for self-host); edit if yours differs. Enforce only after a clean period.
- **Tokens issued before the session change** (no `jti`/`ver`) stay valid until they expire (max 8 h) and cannot be revoked individually.
- **No customer self-cancel**, refunds are admin-driven; refund calls have no idempotency key at Razorpay (the local reservation protects against double-clicks, not against a crash between the Razorpay call and saving state: that case is logged as `REFUND ISSUED BUT STATE NOT SAVED` for manual reconciliation).

**Data growth (small fixes, not done)**
- `rate_limit_events` rows are pruned only when the *same key* is checked again, so keys of visitors who never return accumulate forever. A one-line `DELETE ... WHERE ts < now - 1 day` in `/internal/sweep` fixes it.
- `otp_codes` (expired rows), `audit_log`, `notification_messages` have no retention policy. Fine for months; add pruning before it matters.
- Admin pagination is offset-based (fine for one venue). Audit log, notification log and gallery lists are not all paged.

**Testing**
- CI (`deploy.yml`) runs the backend suite with `uv sync --frozen`, so the new dependencies (`boto3`, `sentry-sdk`) install, but the suite has **never run on Linux**; expect the first CI run might surface path or platform assumptions. It does not run Playwright or Postgres.

## 5. Ordered checklist for the first production deploy

Tick each box; stop and fix anything that fails before moving on.

### A. Decide and gather (no deploy yet)
- [ ] **Domains.** Put web, admin, kiosk and API under one registrable domain (for example `book.`, `admin.`, `pos.`, `api.` + your domain) with custom domains attached in Cloudflare/Render. If you cannot, plan `DAZY_COOKIE_SAMESITE=none` and test it (step 11).
- [ ] **Credentials ready:** Razorpay live **and** test keys + a webhook secret; R2 account id, access key id/secret, bucket and a public hostname; Turnstile site key + secret (add all your web hostnames); Sentry DSN; an SMTP account for the venue's sender address; a long random `JWT_SECRET` (32+ chars), `DAZY_INTERNAL_TOKEN` (32+ chars), and an admin password: generate a bcrypt hash for `ADMIN_PASSWORD_HASH` (command in `.env.example`; escape `$` as `$$` only in compose files).
- [ ] **Start the slow approvals now:** WhatsApp templates (utility: confirmed, cancelled, refunded; authentication: OTP) in Meta Business Manager, and DLT template registration + MSG91 flows. Exact texts and variable order are in App-Overview 4.7. Everything else can go live without them; those channels will show as *skipped*.
- [ ] **Confirm the refund policy** tiers (default 100% ≥ 24 h, 50% ≥ 4 h, else 0%) with the owner, and that the owner knows Cancel on a paid booking now opens a refund dialog.

### B. Rehearse the database change (no production impact)
- [ ] Create a **Neon branch** (copy) of production data.
- [ ] Run the dry-run against it: `DAZY_DB_URL=<branch url> uv run python scripts/check_fk_orphans.py`. Read the orphan report; it exits 1 if anything would be repaired. (The migration repairs automatically and deletes nothing.)
- [ ] Run the Postgres migration test against a throwaway database: `DAZY_TEST_PG_URL=postgresql+psycopg2://…/dazy_test uv run pytest tests/test_foreign_keys.py -q` (it wipes that database's schema; the name must contain `test`). It should pass, not skip.
- [ ] Boot the API once against the **branch** (`DAZY_DB_URL=<branch url> uv run uvicorn main:app`) and watch the log: the 9 new migrations apply, `startup: complete`, `GET /api/v1/health/ready` returns 200 with `migrated: true`.

### C. Stage it (recommended; skip only if you accept testing on production)
- [ ] Create a second Render service from the same repo pointing at a **non-`main` branch** (push the Phase 2 commits to a `release/phase2` branch, not `main`), with `DAZY_ENV=production`, the Neon **branch** URL and **test-mode** Razorpay keys. Frontends: Cloudflare preview deployments with `VITE_API_BASE_URL` and `VITE_TURNSTILE_SITE_KEY`.
- [ ] If the service fails to boot, the log names the missing setting (the guard lists every problem at once). Fix and redeploy.

### D. Configure production (still before pushing `main`)
- [ ] **Take a Neon backup/branch of production** and note your restore window.
- [ ] Render env (see `render.yaml` for every name; secrets are entered in the dashboard): `JWT_SECRET`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `DAZY_DB_URL` (pooled), `DAZY_CORS_ORIGINS` (exact origins, no trailing slash), `DAZY_WEB_BASE_URL`, `DAZY_PAYMENT_PROVIDER=razorpay` + `RAZORPAY_KEY_ID/SECRET/WEBHOOK_SECRET`, `TURNSTILE_SECRET`, `R2_*` + `DAZY_MEDIA_BACKEND=r2`, `DAZY_INTERNAL_TOKEN`, `DAZY_PROXY_HOPS`, `DAZY_NOTIFY_PROVIDER=email` + `SMTP_*`, `SENTRY_DSN`. `DAZY_ENV=production` is already in `render.yaml`. Leave `DAZY_RATE_LIMIT_SCALE` unset (production refuses to boot otherwise).
- [ ] Cloudflare build variables for **each** SPA: `VITE_API_BASE_URL=https://<api host>/api/v1`; for the web build also `VITE_TURNSTILE_SITE_KEY`. Edit the three `public/_headers` files if the API origin is not `https://api.dazyclub.com`.
- [ ] **Razorpay dashboard:** register `https://<api host>/api/v1/payments/razorpay/webhook` with the webhook secret and events `payment.captured` (and `payment.failed`, which is logged).

### E. Deploy and verify, in this order
1. [ ] **Push `main`** (this deploys). Watch the Render log: guard passes, migrations apply, `startup: complete`, then any `NOTIFICATIONS:` warnings (each names a channel that will not deliver).
2. [ ] `GET https://<api>/api/v1/health/ready` → 200, `migrated: true`, `db: ok`. `GET .../health` → 200.
3. [ ] **Response headers:** a request returns `X-Request-ID`, `X-Content-Type-Options: nosniff`; admin responses carry `Cache-Control: no-store`.
4. [ ] **Run the smoke test:** `python scripts/smoke_test.py --base-url https://<api> --admin-username … --admin-password …`.
5. [ ] **Sign in to admin on the real domain.** In browser devtools: the `dazy_admin` cookie is `HttpOnly`, `Secure`, correct `SameSite`; nothing token-like in localStorage; reload keeps you signed in; **Logout** then a copied API call returns 401. Do the same on the kiosk. If login "works" but pages bounce back to login, it is the cookie/site problem from section 3.1.
6. [ ] **Rate-limit IP check:** call any limited endpoint (e.g. `/api/v1/bookings/lookup?ref=X&contact=1234567890`) and confirm the access log's `ip` is **your** address, not a proxy's. Adjust `DAZY_PROXY_HOPS` if not.
7. [ ] **Turnstile:** make a booking and submit the contact form from the real web domain; both succeed.
8. [ ] **A real test booking end to end** (test-mode keys first if you staged; otherwise a small live amount): pay, receive the confirmation email, see it in Admin → Bookings and Admin → Notifications (`sent`). Then **cancel & refund** part of it and confirm the refund appears in the Razorpay dashboard and the customer got the refund email.
9. [ ] **Webhook path:** in Razorpay, confirm the webhook delivery log shows 200 for that payment.
10. [ ] **Gallery:** upload an image, confirm its URL is on your R2 hostname, **redeploy**, and confirm it still loads.
11. [ ] **Schedule the cron worker:** `infra/cron-worker/` (`wrangler secret put INTERNAL_TOKEN`, `wrangler deploy`), trigger it once from the dashboard, then check `/health/ready` shows `sweep.lastRunAt` and the API log shows the `cron-` request id. Add a Cloudflare notification for failed cron invocations.
12. [ ] **Uptime monitor** on `GET /api/v1/health/ready` every 5 minutes, alerting on non-200.
13. [ ] **Sentry:** trigger a harmless error (or check the first event) and confirm it arrives with a request id and without contact details.
14. [ ] **CSP:** with the browser console open, walk through booking, payment (Razorpay checkout) and admin pages on the real domains; there should be no report-only violations. Only then rename `Content-Security-Policy-Report-Only` to `Content-Security-Policy` in the three `_headers` files and `Caddyfile`.
15. [ ] When templates/accounts are approved: set the WhatsApp/MSG91 variables, send one booking through each channel to a test phone, and confirm `sent` in Admin → Notifications; test an OTP search from a phone-only contact.

### F. First week
- [ ] Check Admin → Notifications → *Failed* daily; Sentry; `/health/ready` alerts; the Razorpay dashboard for payments with no booking (`paid_orphan` / `amount_mismatch` appear in the audit log and logs).
- [ ] Add the one-line `rate_limit_events` prune and decide retention for audit/notifications.
- [ ] Add a CI job on Linux + Postgres (the biggest remaining testing gap) and a Playwright smoke job.

## 6. If something goes wrong

| Symptom | First thing to check |
|---|---|
| API will not start, log lists settings | The production guard: set each named variable. No database was touched |
| API starts, `/health/ready` is 503 `migrated: false` | A migration did not apply: read the startup log; fix forward or restore the Neon backup |
| Everyone gets 429 | `DAZY_PROXY_HOPS` too high (all visitors share one address) |
| Staff signed in but every page returns to login | Cookie is not sent: SPA and API on different sites → one parent domain or `DAZY_COOKIE_SAMESITE=none`; also check `DAZY_CORS_ORIGINS` |
| Booking/contact forms say "complete the verification" | Turnstile secret/site-key mismatch or hostname not on the widget's list |
| Customer paid but no booking | Audit log `payment.*` events; Razorpay payment id; `paid_orphan` rows need a manual refund |
| No emails/SMS/WhatsApp | Startup `NOTIFICATIONS:` warnings; Admin → Notifications statuses and error text |
| Expired bookings linger / retries never fire | Cron worker not running: `sweep.lastRunAt` on `/health/ready` |
| Need to undo the deploy | Redeploy the previous commit (probably safe, untested); for data, restore the pre-deploy Neon backup |
