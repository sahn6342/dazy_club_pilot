# System Architecture

## Launch Architecture
- `apps/web`: public React/Vite website for browse and enquiry.
- `apps/api`: FastAPI (Python 3.12) API for public content and enquiry persistence.
- PostgreSQL: primary database for seeded content and enquiries.
- `packages/ui`: shared UI components after code implementation begins.
- `packages/shared`: shared contracts and types.
- `packages/config`: shared tooling config.

## Deferred Architecture
- `apps/admin`: admin shell first, full workflows later.
- Redis: future slot locks, cache, and realtime support.
- SignalR: future availability updates.
- Background jobs: future notifications, CRM tasks, and payment reconciliation.
- Cloud storage/CDN: future media delivery.

## External Services
Payment and OTP providers are deferred. Architecture must expose adapter boundaries and avoid hardcoded provider assumptions.
