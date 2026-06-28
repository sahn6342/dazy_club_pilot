# Dazy.club Pilot

Dazy.club is a premium sports experience platform. This pilot implements the first launch slice: public browse and enquiry for Cricket, Badminton, and Pickleball. updated

## Scope
- Launch: public website, seeded content, gallery/testimonials, contact enquiry, corporate enquiry.
- Deferred: live booking, OTP, payment, full admin CMS, CRM automation.

## Repo Layout
- `apps/web` - React/Vite public website.
- `apps/admin` - future admin shell.
- `apps/api` - ASP.NET Core 9 API shell.
- `packages/ui` - shared UI primitives.
- `packages/shared` - shared data/contracts.
- `packages/config` - shared config placeholders.
- `infra` - local infrastructure notes.
- `docs` - source of truth.

## Useful Commands
- `pnpm install`
- `pnpm dev`
- `pnpm build`
- `pnpm typecheck`

The local machine must have a .NET 9 SDK installed before the API can be built exactly as documented. This repo includes `global.json` to keep the backend aligned with the accepted .NET 9 ADR.
