# Infrastructure

Production deploy is a single Docker Compose stack: FastAPI (`api`), three static Vite SPAs (`web`/`admin`/`kiosk`), and Caddy in front for automatic HTTPS across all four hostnames. SQLite + uploaded media persist in one named volume.

Full setup, env vars, backups, and the demo-content-removal + smoke-test steps: **[docs/Docker-Deployment.md](../docs/Docker-Deployment.md)**.

Future infrastructure (see `docs/Roadmap.md` / `docs/Detailed-Roadmap.md`):
- PostgreSQL — swap `DAZY_DB_URL`, zero code changes (repository pattern).
- Redis for slot locking at higher concurrency.
- Cloud storage/CDN for media (currently local `/data/media`, served via FastAPI StaticFiles).
