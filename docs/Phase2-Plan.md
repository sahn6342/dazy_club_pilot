# Phase 2 plan — production readiness

Follows Phase 0 (`d5b0437`) and Phase 1 (`a8d301b`). Source: the architecture review of
[App-Overview.md](App-Overview.md), items 13–17, with the decisions below already made.

## Decisions (made)

| Topic | Decision |
|---|---|
| Media | Cloudflare R2 (S3-compatible) behind a storage adapter; local disk stays for dev |
| Staff sessions | httpOnly Secure cookie + CSRF header + logout + per-user `token_version` |
| Refunds | Tiered by notice (configurable in CMS), admin "Cancel & refund" with optional override; no customer self-cancel |
| Date columns | **Not** converting strings to `DATE/TIMESTAMPTZ` now. Add real FKs and indexes only |
| Monitoring | Sentry (errors) + JSON logs with request ids + external uptime check (my default; say if you want otherwise) |

## What I need from you (cannot be done from the repo)

1. **R2**: create a bucket, an API token (Object Read & Write), and a public hostname (e.g. `media.dazyclub.com` or the `r2.dev` URL). Provide: account id, access key id/secret, bucket name, public base URL.
2. **Cookie domain**: confirm admin, kiosk, web and API all sit under one registrable domain (e.g. `admin.dazyclub.com`, `pos.dazyclub.com`, `api.dazyclub.com`). Cookies need that; if a frontend is on a `*.pages.dev` URL it will not work until a custom domain is attached.
3. **Render plan**: upgrade from free (no sleep, no lost state). Neon: use the pooled connection string.
4. **Sentry** project DSN (free tier is enough).
5. **Refund tiers**: confirm the default (100% if more than 24 h before start, 50% from 4–24 h, 0% under 4 h).
6. **SMS vendor** for phone-only customers (MSG91 is the usual fit in India; needs DLT template ids), and WhatsApp template approval in Meta Business Manager. Without these the notification work below can only be built against mocks.

## Workstreams, in build order

### A. Media on R2 (unblocks real gallery use) — ~1 day
- `media_store.py` becomes a storage interface: `LocalStorage` (today's behaviour) and `R2Storage` (boto3 `put_object` / `delete_object`), chosen by `DAZY_MEDIA_BACKEND=local|r2`.
- Gallery upload/delete (`routes/admin/gallery.py`) call the interface; stored `imageUrl` is the public R2 URL. Existing `/media/...` rows keep working while the local mount exists.
- Env: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_PUBLIC_BASE_URL`; added to `render.yaml`, `.env.example`, compose and the production guard (R2 required in production unless a disk is configured).
- Tests with a stubbed S3 client (moto-style fake), including magic-byte rejection still applying.

### B. Staff sessions: cookies, logout, revocation — ~2–3 days
- `users.token_version` (migration). Tokens carry `ver`; every request compares it, so logout/password change/role change/delete revoke instantly. Env admin: `ADMIN_SESSION_EPOCH` env bump revokes.
- Login sets `dazy_session` (httpOnly, Secure, SameSite=Lax, `Domain=DAZY_COOKIE_DOMAIN`, same TTLs as today). `POST /admin/logout` and `/cafe/logout` clear it and bump `token_version`. `GET /admin/me` and `/cafe/me` bootstrap the SPA.
- CSRF: state-changing requests authenticated by cookie must send `X-Requested-With: dazy` (cross-site forms cannot set it; CORS preflight blocks other origins). Bearer tokens remain accepted for scripts/tests and need no CSRF header.
- CORS: `allow_credentials=True`, explicit origins only (already), `allow_headers` narrowed to the headers we use.
- Frontends (admin, kiosk): drop `localStorage` token code, use `credentials: "include"`, call `/me` on load, add a logout button. Web (customer) unchanged.
- Security headers: Cloudflare `_headers` for each SPA (CSP, HSTS, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, `frame-ancestors 'none'`) plus an API middleware for `nosniff`. CSP must allow Turnstile (`challenges.cloudflare.com`), Razorpay Checkout (`checkout.razorpay.com`, `api.razorpay.com`), R2 images and the API origin. Start `Content-Security-Policy-Report-Only` for a deploy, then enforce.
- Tests: cookie login/logout/revocation, CSRF rejection, Bearer still works, E2E admin + kiosk login flows updated.

### C. Audit trail — ~1 day
- Wire the unused `audit_log` table: helper `audit(actor, role, action, entity, id, detail, ip)`.
- Record: booking status change, cancel, refund, delete, promo create/edit/delete, schedule/court changes, CMS/GST-rate edits, user create/role/password/delete, login failures/lockouts, orphan-payment and amount-mismatch events.
- `GET /admin/audit` (paginated, filter by actor/action/entity/date) and an Audit page in admin. Superadmin only.

### D. Refunds and cancellation policy — ~2 days
- CMS key `refund_policy` (JSON tiers: hours-before-start → percent), default as above.
- `POST /admin/bookings/{id}/cancel-and-refund`: computes the policy amount from the booking start time, accepts `amountOverride` (≤ paid), calls `provider.refund(payment_id, amount)`, cancels the booking (frees the slot), marks payment, notifies the customer with the amount, audits it.
- Partial refunds: `booking_payments.refunded_amount`, `bookings.paymentStatus` gains `partially_refunded`; refunding again is limited to the remaining balance; existing full-refund endpoint stays and uses the same code path.
- Admin UI: one "Cancel & refund" dialog showing the policy result and override field.
- Tests: tier boundaries (exactly 24 h / 4 h, venue timezone), override cap, double refund blocked, provider failure leaves state unchanged, free/unpaid bookings.

### E. Admin scalability and safe deletes — ~1–2 days
- Replace `booking_repo.get_all()` + Python filter/sort with a SQL `query(filters, sort, limit, offset)` + `count`; same for customers and enquiries (they also load everything). Add indexes `(date, status)` and a normalised `contact_norm` column (written on create, indexed) used by search, the pending cap and customer upsert.
- CSV export streams rows (`StreamingResponse`) instead of returning a giant JSON list.
- Soft delete for bookings (`deleted_at`): hidden from lists/availability, blocked outright for paid bookings or ones with linked orders/invoices, audited. Hard delete only via a superadmin purge.
- Tests with a few thousand seeded bookings asserting query count and page contents.

### F. Notifications that reach phone-only customers — ~2 days (blocked on vendor/template approval)
- WhatsApp templates for pending / confirmed / cancelled / refunded through the existing Cloud API adapter (today it only sends free text, which WhatsApp drops outside a 24 h window).
- SMS provider behind the existing `sms_provider` interface (MSG91 flow API, DLT template ids in env).
- Retry: failed sends are retried (max 3, backoff) by `/internal/sweep`; the admin notification log shows failures and a manual resend.
- Production guard: warn loudly if phone numbers are accepted but only stubs are configured.

### G. Observability and ops — ~1 day
- `GET /health` stays cheap (Render check); new `GET /health/ready` does `SELECT 1` plus migration revision, for the uptime monitor.
- Sentry SDK (`SENTRY_DSN`, `SENTRY_ENV`, release = git sha), with PII scrubbing (no contact details, tokens, OTPs); tracing off.
- JSON logs with a request-id middleware (method, path, status, duration, client ip); remove the print-based notification stubs from prod paths.
- `infra/cron-worker/`: a Cloudflare Worker with a 2-minute cron trigger that POSTs `/internal/sweep` (also keeps the instance warm). Document the uptime check and Render/Neon settings in `render.yaml` comments.

### H. Referential integrity (no type migration) — ~1 day
- Migration: null/repair orphan `bookings.court_id` / `customer_id` first, then add real FKs (batch alter for SQLite), plus `orders.booking_id` and `orders.customer_id`.
- Verified on a Postgres copy before shipping; SQLite path covered by pytest.

## Order and dependencies

A → B → C → D → E → H → G → F.
A first because it is a production data-loss bug. C before D so refunds are audited from day one. B before CSP enforcement. F last: external approvals take days, start the Meta/MSG91 paperwork now.

## Risks

- Cookies + CORS credentials are the most failure-prone change (domains, `Secure`, Safari ITP). Mitigation: Bearer stays accepted, ship behind `DAZY_COOKIE_AUTH=1`, test on staging domains before enforcing.
- CSP can silently break Razorpay/Turnstile. Mitigation: report-only first.
- FK migration can fail on dirty data. Mitigation: dry-run script that reports orphans before any ALTER.
- R2 public URL changes break old gallery rows if the base URL changes. Mitigation: store keys, build URLs from `R2_PUBLIC_BASE_URL`.

## Verification

- `uv run pytest tests -q` green after each workstream, plus new tests listed above.
- Per workstream E2E on a fresh DB with the API pinned to `noop` and `DAZY_RATE_LIMIT_SCALE=100` (admin/kiosk login specs change in B).
- Staging checklist before any production deploy: real Razorpay test payment incl. a partial refund, R2 upload survives a redeploy, cookie login on the real subdomains, CSP report-only clean, Sentry receives a forced error, `/internal/sweep` fires from the Worker, WhatsApp/SMS delivered to a test phone.

## Explicitly out of scope

Customer self-cancel, string→`DATE/TIMESTAMPTZ` migration, Postgres-in-CI and concurrency tests (Phase 3), multi-instance scaling beyond what the DB-backed limiter already allows.
