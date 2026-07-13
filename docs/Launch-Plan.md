# Dazy.club — Launch Plan (Domain, Hosting, Deployment)

> Referenced from [Detailed-Roadmap.md](Detailed-Roadmap.md)'s 🚀 GO LIVE section ("run the go/no-go checklist from `Launch-Plan.md §5`"). Technical deploy mechanics live in [Docker-Deployment.md](Docker-Deployment.md) — this doc covers the business/ops decisions (domain, hosting provider, cost) and sequences them into one checklist.

## 1. Domain — decided

**`dazyclub.in`** — Porkbun, **$7.83/yr flat** (registration = renewal, no promo/renewal-shock gap). `.in` has been open to global registrants since 2005, no local-presence requirement.

Four subdomains (free, one purchase covers all): `book.` `admin.` `pos.` `api.dazyclub.in`.

Considered and rejected: `dazy.club` (brand-exact match, but `.club` renewal jumps ~3x after a promo year) and `dazyclub.com` (safest TLD, but breaks the "Dazy.club" brand string). `.env.example` and `docs/Docker-Deployment.md` are already wired for `dazyclub.in`.

## 2. Hosting — decided

**Primary: Oracle Cloud Always Free** — ₹0/month forever, region *India South (Hyderabad)* or *India West (Mumbai)*, `VM.Standard.A1.Flex` ARM instance (free tier = 2 OCPU / 12GB as of June 2026, plenty for this app). The existing `docker-compose.yml` stack (api + web + admin + kiosk + Caddy) runs unchanged — all images used are multi-arch.

Known friction: ARM capacity in a given region is sometimes "out of stock" at signup time. **Time-box to one evening**; if it doesn't work out, fall back immediately rather than fighting it further.

**Fallback: Vultr or Linode (Akamai), Mumbai region** — ~$6/mo (~₹500), zero capacity games, same deploy steps. Reasonable to just start here if Oracle friction isn't worth the free-vs-₹500/mo tradeoff for the user.

Rejected: Render/Koyeb free tiers (no persistent disk — would wipe the SQLite DB on every redeploy, plus cold-start delays mid-checkout); Fly.io (would need repackaging away from the existing compose/Caddy setup for no real benefit at this scale).

## 3. Repo readiness — done

- `docker-compose.yml` — api service passes through `DAZY_PAYMENT_PROVIDER`, `RAZORPAY_KEY_ID/SECRET/WEBHOOK_SECRET`, `DAZY_NOTIFY_PROVIDER`, `SMTP_*`, derives `DAZY_WEB_BASE_URL` from `WEB_DOMAIN`. All have safe `${VAR:-default}` fallbacks (noop/console) so a deploy without real keys still boots.
- `.env.example` — filled in with the real `dazyclub.in` subdomains and every new var, ready to `cp` and fill secrets.
- `docs/Docker-Deployment.md` — env var table + a new "Razorpay webhook" section with the exact registration steps.

No application code changes were needed — the payment/notification adapters (`apps/api/integrations/{payments,notifications}/`) already read these vars via their `factory.py` modules.

## 4. Deploy sequence

1. **Buy `dazyclub.in`** at Porkbun.
2. **Add it to a free Cloudflare DNS zone** — point Porkbun's nameservers at Cloudflare. Create 4 `A` records (`book`/`admin`/`pos`/`api`) → the server's public IP, **DNS-only (gray cloud)** at first so Caddy can issue Let's Encrypt certs; flip the proxy on later if wanted (CDN/DDoS), with SSL mode "Full (strict)".
3. **Provision the server** (Oracle primary / Vultr-Linode fallback, §2). Open ports 80/443 in both the cloud firewall (VCN Security List on Oracle) and the OS firewall (`ufw`).
4. **Install Docker** (`curl -fsSL https://get.docker.com | sh`) + the compose plugin.
5. **Wait for DNS to propagate** before starting Caddy (it requests certs on boot and will fail/retry otherwise).
6. **Deploy**: `git clone`, `cp .env.example .env`, fill in real values — the four `dazyclub.in` subdomains (already defaulted), a long random `JWT_SECRET`, real `ADMIN_USERNAME`/`ADMIN_PASSWORD`, `DAZY_PAYMENT_PROVIDER=razorpay` + the existing **test** Razorpay keys, `DAZY_NOTIFY_PROVIDER=console` for now. Then `docker compose up -d --build`.
7. **Register the Razorpay webhook** — dashboard → `https://api.dazyclub.in/api/v1/payments/razorpay/webhook`, event `payment.captured` → copy the secret into `.env` → `docker compose up -d api`.
8. **Remove demo content**: `docker compose exec api python scripts/reset_demo_content.py --yes`, then add real gallery/testimonials/promos and venue details via the admin app.
9. **Set up backups**: nightly cron tarring the `api_data` volume (`dazy.db` + media) to Oracle Object Storage (20GB always-free) or any rclone target.
10. **Switch to live Razorpay keys** once KYC clears — one `.env` edit + `docker compose up -d api`. Optionally switch `DAZY_NOTIFY_PROVIDER=email` with real SMTP creds at the same time.

## 5. Go/no-go checklist

Run this before opening to real customers, and again after any change to payment/booking code:

- [ ] All 4 hostnames resolve and serve valid HTTPS (`docker compose logs caddy` shows cert issuance for each)
- [ ] `curl https://api.dazyclub.in/api/v1/health` → `{"status":"ok"}`
- [ ] Full booking end-to-end on `https://book.dazyclub.in`: priced slot → Razorpay **test** checkout → test card → "BOOKING CONFIRMED"
- [ ] Razorpay dashboard shows the webhook delivering `200` for that booking
- [ ] Booking appears correctly in `https://admin.dazyclub.in` → Bookings
- [ ] A notification row appears in `GET /admin/notifications` for that booking
- [ ] `/my-bookings` on the live site correctly resumes a pending payment (book a slot, close the tab, look it up again)
- [ ] Kiosk login works at `https://pos.dazyclub.in` with a real cashier PIN; a café order + GST invoice prints correctly
- [ ] Reboot the VM (`sudo reboot`) → all 5 containers auto-restart (`docker compose ps`), booking/café data intact
- [ ] `ADMIN_USERNAME`/`ADMIN_PASSWORD` changed off `admin`/`admin`; `JWT_SECRET` is a real random string
- [ ] Demo content removed (`reset_demo_content.py --yes` run); real venue details in CMS
- [ ] Backup cron job installed and has produced at least one successful backup
- [ ] Switched to **live** Razorpay keys only after the above all pass on test keys, and after Razorpay KYC is approved

Soft-launch with a handful of real bookings once this checklist is green; watch `docker compose logs -f api` during those first bookings, then open up fully.

## 6. CI/CD (`.github/workflows/deploy.yml`)

Deploys on push to `main` **and** on-demand via the Actions tab's "Run workflow" button (`workflow_dispatch`). A `test` job (backend pytest + all-frontend typecheck/build) must pass before `deploy` runs — a bad merge never reaches production.

**One-time setup on GitHub** (repo → Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `DEPLOY_HOST` | The server's public IP |
| `DEPLOY_USER` | SSH login user (e.g. `ubuntu`) |
| `DEPLOY_SSH_KEY` | The **private** key matching a public key already in the server's `~/.ssh/authorized_keys` |
| `DEPLOY_PATH` | Absolute path to the repo clone on the server (e.g. `/opt/dazy_club_pilot`) |
| `DEPLOY_PORT` | Optional — only needed if SSH isn't on port 22 |

The deploy step runs `git pull --ff-only` on the server, not a force-reset — **never hand-edit files in the server's repo clone**, or the pull will fail and block deploys until it's fixed manually.

Optional extra safety net: repo → Settings → Environments → create `production`, add yourself as a required reviewer. The `deploy` job already targets `environment: production`, so this alone adds a manual-approval gate in front of every deploy (including auto-triggered ones) with no workflow-file change.

## 7. Cost (year 1)

| Item | Cost |
|---|---|
| Domain `dazyclub.in` (Porkbun) | ~₹650–700/yr |
| Hosting (Oracle Always Free) | **₹0** (fallback Mumbai VPS: ~₹6,000/yr) |
| TLS + DNS (Let's Encrypt + Cloudflare free) | ₹0 |
| Backups (Oracle Object Storage free tier) | ₹0 |
| **Total** | **~₹700/yr** (or ~₹6,700/yr on the paid-VPS fallback) |
