# Naming Standards

## Python / FastAPI
- Files: `snake_case.py`
- Classes: `PascalCase` (models, repos, services)
- Functions / variables: `snake_case`
- DB column names: `camelCase` (SQLAlchemy `mapped_column` — matches existing schema)
- Pydantic models: `PascalCase` — suffix `Dto` for responses, `Create`/`Update` for inputs

## TypeScript (React)
- Files: `PascalCase.tsx` for components/pages, `camelCase.ts` for libs
- Components / pages: `PascalCase`
- Variables / functions: `camelCase`
- Types / interfaces: `PascalCase`
- CSS classes: `kebab-case`

## API
- Endpoints: `kebab-case` (`/admin/schedule/exceptions`)
- Query params: `snake_case` (`?sport=cricket&date=2026-07-01`)
- JSON keys: `camelCase` in responses (`courtId`, `startTime`, `finalPrice`)

## Database
- Tables: `snake_case` plural (`schedule_rules`, `promo_codes`)
- SQLAlchemy row classes: `PascalCase` + `Row` suffix (`CourtRow`, `BookingRow`)
- IDs: text UUIDs or human-readable slugs (`court-cricket`, `venue-dazy`)

## IDs / Slugs
- Sport slugs: `cricket`, `badminton`, `pickleball`
- Court IDs (seeded): `court-{sport}` → `court-cricket`, `court-badminton`, `court-pickleball`
- Venue ID (seeded): `venue-dazy`
- Slot IDs: `slot-{court.id}-{date}-{HHMM}` → `slot-court-cricket-2026-07-01-0600`
