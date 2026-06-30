# Decision Log

| ID | Decision | Status |
|---|---|---|
| DEC-001 | Documentation-first AI workflow | Superseded (docs pruned) |
| DEC-002 | Figma-first design | Skipped (went straight to code) |
| DEC-003 | pnpm monorepo | Accepted |
| DEC-004 | ASP.NET Core 9 backend | Superseded by DEC-011 |
| DEC-005 | React + Vite + TypeScript (web/admin) | Accepted |
| DEC-006 | PostgreSQL primary DB | Deferred — using SQLite for pilot |
| DEC-007 | Defer payment provider | Accepted |
| DEC-008 | Defer OTP/SMS provider | Accepted |
| DEC-009 | Launch without live booking | Superseded — booking is live |
| DEC-010 | Seeded demo content | Accepted |
| DEC-011 | FastAPI (Python 3.12) replaces ASP.NET | Accepted — see ADR-011 |
| DEC-012 | Resource-scheduling domain model | Accepted — see ADR-012 |
| DEC-013 | JWT auth with env-var + DB managers | Accepted |
| DEC-014 | SQLite for pilot, swap via DAZY_DB_URL | Accepted |
| DEC-015 | Soft-delete courts; slot IDs include court.id | Accepted |
| DEC-016 | Venue-wide exceptions via court_id=NULL | Accepted |

## Open
- Production hosting / deployment provider
- PostgreSQL migration timeline
- Payment provider selection
- SMS/OTP provider selection
- Final brand assets (logo, copy, photos)
