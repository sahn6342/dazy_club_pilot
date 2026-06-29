# Deployment Architecture

## Launch Target
Deployment provider is open. The architecture must support:
- Static/public frontend hosting for `apps/web`.
- FastAPI/uvicorn hosting for `apps/api` (ASGI-compatible host or container).
- PostgreSQL database.
- Environment variables for secrets and endpoints.

## Future
- Redis for cache/slot locks.
- CDN and cloud storage for media.
- Background job worker.
- Admin app hosting.

## Release Path
Alpha -> Internal Beta -> Closed Beta -> Soft Launch -> Public Launch.
