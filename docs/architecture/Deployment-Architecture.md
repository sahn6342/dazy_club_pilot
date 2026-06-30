# Deployment Architecture

## Local / Dev

```
pnpm dev:web   →  Vite dev server  :5173
pnpm dev:admin →  Vite dev server  :5174
uvicorn main:app --reload  :8000
```

## Production (planned)

| Component | Approach |
|---|---|
| Web (`apps/web`) | `pnpm build` → static files → Vercel / Netlify / S3 |
| Admin (`apps/admin`) | `pnpm build:admin` → static files → private static host |
| API (`apps/api`) | Docker container → Railway / Fly.io / AWS Fargate |
| Database | PostgreSQL — change `DAZY_DB_URL` env var |
| Media | Static files at `/media/gallery/` in container → move to S3 for prod |

## Docker (API)

```bash
docker build -t dazy-api apps/api
docker run -p 8000:8000 \
  -e DAZY_DB_URL=postgres://user:pass@host/dbname \
  -e JWT_SECRET=... dazy-api
```

## Required env vars (prod)

```
DAZY_DB_URL         postgres://user:pass@host/dbname
ADMIN_USERNAME      (strong value)
ADMIN_PASSWORD      (strong value)
JWT_SECRET          (32+ char random string)
```
