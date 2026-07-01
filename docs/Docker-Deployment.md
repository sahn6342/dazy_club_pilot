# Docker Deployment

Production deploy: one VPS running Docker, four public hostnames (web / admin / kiosk / api), Caddy in front for automatic HTTPS, SQLite + uploaded media on a single persistent volume.

```
Internet
   │
   ▼
┌─────────────────────────── caddy (ports 80/443) ───────────────────────────┐
│  book.example.com   → web:80       admin.example.com → admin:80            │
│  pos.example.com    → kiosk:80     api.example.com   → api:8000            │
└──────────────────────────────────────────────────────────────────────────┘
   web / admin / kiosk = static Vite builds (Caddy file_server, SPA fallback)
   api = FastAPI container, /data volume (dazy.db + media/)
```

## Prerequisites

- **Production:** a VPS (any provider) with Docker + Docker Compose installed.
- DNS A/AAAA records for all four domains pointing at the VPS, **already propagated** before first start (Caddy requests Let's Encrypt certs on boot and will fail/retry if DNS isn't live yet).
- Ports 80 and 443 open.

**Local development:** the same `docker-compose.yml`/`Dockerfile`s work unchanged with **Podman** — no compose file edits needed, Podman consumes standard Dockerfiles and Compose files directly. Everywhere below that says `docker compose`, substitute `podman compose` (Podman Desktop bundles this; standalone Podman needs the `podman-compose` package or Podman ≥4.x's built-in compose provider). On Windows/macOS, start the Podman machine first: `podman machine init && podman machine start` (Docker Desktop's equivalent of this is automatic). One thing to point local domains (`book.localhost` etc.) at `127.0.0.1` for a local Caddy test — either edit your hosts file or skip Caddy locally and hit each service's `expose`d port directly via `podman compose port <service> 80`.

## First deploy

```bash
git clone <repo> && cd dazy_club_pilot
cp .env.example .env
# edit .env: real domains, JWT_SECRET, ADMIN_USERNAME, ADMIN_PASSWORD — see below.
docker compose up -d --build
```

This builds and starts 5 containers: `api`, `web`, `admin`, `kiosk`, `caddy`. On first boot the API auto-runs Alembic migrations and seeds demo content into empty tables (`init_db()` + `seed_if_empty()` in `main.py`'s lifespan) — see **Removing demo content** below.

Check it came up:

```bash
docker compose ps
docker compose logs -f api      # watch for migration/seed lines, then "Uvicorn running"
docker compose logs -f caddy    # watch for cert issuance per domain
```

## Environment variables (`.env`, see `.env.example`)

| Var | Purpose |
|---|---|
| `WEB_DOMAIN`, `ADMIN_DOMAIN`, `KIOSK_DOMAIN`, `API_DOMAIN` | Public hostnames Caddy issues certs for and routes to each service |
| `JWT_SECRET` | Signs auth tokens — **must** be a long random string, not the dev default |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | The env-var superadmin login — **must** be changed off `admin`/`admin` |

`docker-compose.yml` derives the rest automatically:
- Each frontend is built with `VITE_API_BASE_URL=https://${API_DOMAIN}/api/v1` baked in at build time (Vite env vars are compile-time, not runtime — changing `API_DOMAIN` requires a rebuild: `docker compose up -d --build`).
- The API's `DAZY_CORS_ORIGINS` is derived from the three frontend domains automatically.
- The API's `DAZY_DB_PATH`/`DAZY_MEDIA_DIR` default to `/data/dazy.db` / `/data/media` inside the container (set in `apps/api/Dockerfile`) — no `.env` entry needed.

**Postgres later:** set `DAZY_DB_URL` on the `api` service in `docker-compose.yml` (e.g. `postgresql://...`) — the repository pattern means zero code changes (see ADR-011/DEC-014). Not needed for pilot volume.

## Data & backups

Everything that must survive a redeploy lives in the `api_data` named volume: `dazy.db` and `media/`. Back it up regularly:

```bash
# Simple periodic backup (cron this)
docker compose exec -T api sh -c 'cat /data/dazy.db' > backup-$(date +%F).db
docker run --rm -v dazy_club_pilot_api_data:/data -v "$PWD":/backup alpine \
  tar czf /backup/media-$(date +%F).tar.gz -C /data media
```

Restoring: stop the `api` service, replace the files inside the volume, start it again.

`caddy_data` holds TLS certificates — losing it just means Caddy re-issues certs on next boot (rate-limited by Let's Encrypt if done too often; not a data-loss risk).

## Removing demo content

The seeded gallery photos, testimonials, and promo codes (`WELCOME10`/`FLAT100`) are placeholders for local dev. Before opening to real customers:

```bash
docker compose exec api python scripts/reset_demo_content.py            # dry run — shows what would be removed
docker compose exec api python scripts/reset_demo_content.py --yes      # actually remove
```

Then add real gallery photos, testimonials, and promo codes via the admin app (Gallery / Testimonials / Promos pages), and fill in real venue details on the CMS / Contact Details page. There is no default admin *database row* to delete — the superadmin login is entirely controlled by the `ADMIN_USERNAME`/`ADMIN_PASSWORD` env vars above, so changing those off the defaults is sufficient.

## Smoke test

After first deploy (and after any redeploy):

```bash
python scripts/smoke_test.py --base-url https://api.example.com \
  --admin-username <ADMIN_USERNAME> --admin-password <ADMIN_PASSWORD>
```

Checks health, a public booking read, and an authenticated café read. Exits non-zero on the first failure.

## Redeploying (code changes)

```bash
git pull
docker compose up -d --build
```

Migrations run automatically on the `api` container's next start. No manual `alembic upgrade` step.

## Rotating secrets

Edit `.env`, then:

```bash
docker compose up -d --build api          # picks up new JWT_SECRET / admin creds
```

Rotating `JWT_SECRET` invalidates all currently-issued tokens (everyone is logged out) — expected and safe.
