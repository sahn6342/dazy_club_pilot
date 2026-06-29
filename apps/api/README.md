# Dazy.club API

FastAPI backend for the Dazy.club pilot. Serves seeded content for the browse + enquiry experience.

## Dev

```bash
# Requires Python 3.12+ and uv (https://docs.astral.sh/uv/)
uv sync
uv run uvicorn main:app --reload --port 8000
```

Or from repo root: `pnpm api:dev`

Auto OpenAPI docs at `http://localhost:8000/docs`.

## Launch Endpoints
- `GET /api/v1/health`
- `GET /api/v1/sports`
- `GET /api/v1/gallery`
- `GET /api/v1/testimonials`
- `GET /api/v1/notifications`
- `POST /api/v1/contact-enquiries`
- `POST /api/v1/corporate-enquiries`

## Deferred
Booking, payment, OTP, and full admin APIs remain future scope.

## Docker

```bash
docker build -t dazy-api .
docker run -p 8000:8000 dazy-api
```
