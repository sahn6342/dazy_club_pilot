# Decision Log

| ID | Decision | Status | ADR |
|---|---|---|---|
| DEC-001 | Use an AI-assisted documentation-first workflow | Accepted | docs/ADR-001-AI-First.md |
| DEC-002 | Design in Figma before code implementation | Accepted | docs/adr/ADR-002-Figma-First.md |
| DEC-003 | Use monorepo layout for apps and shared packages | Accepted | docs/adr/ADR-003-Monorepo-Structure.md |
| DEC-004 | Use ASP.NET Core 9 / .NET 9 for backend | Superseded | docs/adr/ADR-004-Backend-Dotnet9.md |
| DEC-011 | Replace ASP.NET Core 9 with FastAPI (Python 3.12) | Accepted | docs/adr/ADR-011-Backend-FastAPI.md |
| DEC-005 | Use React, Vite, TypeScript for web/admin | Accepted | docs/adr/ADR-005-Frontend-React-Vite.md |
| DEC-006 | Use PostgreSQL as primary database | Accepted | docs/adr/ADR-006-PostgreSQL.md |
| DEC-007 | Defer payment provider selection behind adapter | Accepted | docs/adr/ADR-007-Deferred-Payment-Adapter.md |
| DEC-008 | Defer OTP/SMS provider selection behind adapter | Accepted | docs/adr/ADR-008-Deferred-OTP-Adapter.md |
| DEC-009 | Launch without live booking | Superseded | docs/adr/ADR-009-Public-Launch-No-Live-Booking.md |
| DEC-010 | Use seeded demo content for first design/build | Accepted | docs/adr/ADR-010-Seeded-Demo-Content.md |
| DEC-012 | In-memory storage with repository pattern for MVP | Accepted | — |
| DEC-013 | JWT auth with env-var credentials for admin | Accepted | — |
| DEC-014 | Multi-role auth: superadmin (env-var) + manager (DB user) | Accepted | — |

## Open Decisions
- Final production payment provider.
- Final production SMS/OTP provider.
- Final brand media, copy, logo, and testimonial approvals.
- Hosting and deployment provider.
- PostgreSQL migration timeline (current: in-memory with repo pattern, swap-ready).

---

## Chat / Build History

### Session 1 — Initial setup and backend migration (2026-06)

**Context:** Project started with ASP.NET Core 9 backend. Decision made to migrate to FastAPI (Python 3.12) for lighter weight, faster iteration, and lower deployment cost. pnpm monorepo retained.

**Decisions made:**
- Dropped .NET 9 / ASP.NET Core 9 (`global.json` deleted, `apps/api/Dazy.Api/` deleted)
- FastAPI chosen: async-native, small footprint, auto-docs at `/docs`, Pydantic v2 validation
- `uv` chosen as Python package manager (pip-compatible, fast lockfile)
- All 16 documentation files updated to reflect Python/FastAPI stack
- ADR-011 written to document the migration decision

**Public site cleanup:**
- Removed all dev-facing/dummy content from public UI (`apps/web/src/main.tsx`)
- Removed "Live booking, OTP, and payment are coming next" messaging
- Updated testimonial names to "Priya R." / "Arjun M."
- Sports highlights rewritten for production-ready copy

**Booking system added:**
- `GET /api/v1/slots?sport=&date=` — 12 time slots/day × 7 days × 3 sports, with pre-seeded unavailable slots
- `POST /api/v1/bookings` — validates slot availability, marks slot unavailable, returns booking ref
- Public web slot grid: sport tabs + date pills + slot chip grid with gold=available, strikethrough=unavailable
- Slot availability resets daily (server restart regenerates from seed)

**Tech decisions:**
- `SlotDto` uses `model_config = {"frozen": False}` to allow `slot.available = False` mutation
- Slot state: in-memory, regenerated at server start from `seed.py`

---

### Session 2 — Admin portal (2026-06)

**Context:** Public site complete. Admin portal needed for managing bookings, enquiries, gallery, testimonials, and CMS content.

**Architecture decisions:**
- Repository pattern: `BaseRepository[T]` abstract base + `InMemory*` concrete impls
- All repos live as singletons in `deps.py` — swap for PostgreSQL by replacing class in deps.py only, zero route handler changes
- JWT auth: `pyjwt` (pure Python), 8-hour expiry, `HS256`
- Admin credentials from env vars: `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `JWT_SECRET`
- Manager accounts: stored in `UserRepository`, bcrypt-hashed passwords

**Admin backend (FastAPI routes):**
| Endpoint | Description |
|---|---|
| `POST /api/v1/admin/login` | Returns JWT; checks env-var admin first, then manager repo |
| `GET/PATCH /api/v1/admin/bookings` | List (sport/date/status filter), update status |
| `GET/PATCH /api/v1/admin/enquiries` | List (type/status filter), mark handled |
| `GET/POST/PATCH/DELETE /api/v1/admin/gallery` | Full CRUD + approve/reject |
| `GET/PATCH /api/v1/admin/testimonials` | List + approve/reject |
| `GET/PUT /api/v1/admin/cms` | List all entries, update by key (7 CMS entries seeded) |
| `GET/POST/PATCH/DELETE /api/v1/admin/users` | Manager CRUD (superadmin only) |

**Auth model:**
- `role=admin` (JWT): env-var superadmin, can access everything including user management
- `role=manager` (JWT): repo manager, can access everything except `/admin/users`
- `require_superadmin` FastAPI dependency guards user management
- `get_current_admin` dependency accepts both roles

**Admin frontend (`apps/admin/`, port 5174):**
- React 19 + Vite + TypeScript + react-router-dom v7
- Login → JWT stored in localStorage → AuthGuard redirects if no token
- Pages: Dashboard (stats cards), Bookings (table + filters), Enquiries (tabs), Gallery (grid), Testimonials (list), CMS (editable fields), Managers (CRUD)
- Sidebar with NavLink-based nav, TopBar with logout

**Errors encountered and resolved:**
- `passlib[bcrypt]` incompatible with Python 3.14 + bcrypt 4.x → replaced with direct `bcrypt` calls
- pnpm `ERR_PNPM_IGNORED_BUILDS` for esbuild → `pnpm install --ignore-scripts` (persists on every install)
- Pydantic models immutable by default → `model_config = {"frozen": False}` on mutable models
- `SlotDto.available` mutation needed `model_config = {"frozen": False}` to allow `slot.available = False`

---

### Session 3 — Manager accounts + test suite (2026-06)

**Context:** Added multi-role access control and a complete pytest test suite.

**Manager account system:**
- `UserRecord` model: id, username, hashed_password, role (manager only), createdAt, createdBy
- `InMemoryUserRepository` with `get_by_username()` method
- `POST /admin/users`: superadmin creates manager accounts (bcrypt-hashed password)
- `PATCH /admin/users/{id}`: password update only
- `DELETE /admin/users/{id}`: hard delete
- `require_superadmin` dependency: checks JWT role=admin, rejects managers with 403

**Test suite (`apps/api/tests/`, 70 tests, all passing):**
| File | Coverage |
|---|---|
| `test_auth.py` | Login (valid/invalid), JWT issuance, token rejection, manager login |
| `test_slots.py` | Slot listing, sport/date filter, required fields, booking marks unavailable |
| `test_bookings.py` | Create (success/validation/double-booking), admin list/filter/status-update |
| `test_enquiries.py` | Contact + corporate submission, admin list/filter/mark-handled |
| `test_admin_gallery.py` | List, approve/reject, delete, 404 handling, auth guard |
| `test_admin_testimonials.py` | List, approve/reject, 404 handling, auth guard |
| `test_admin_cms.py` | List, update, persist, 404 handling, auth guard |
| `test_admin_users.py` | Manager CRUD, password rules, role restriction, manager access scope |

**Test infrastructure:**
- `conftest.py`: `autouse` fixture resets all repos + slot availability before each test
- `client` fixture: `starlette.testclient.TestClient` wrapping FastAPI app
- `admin_token` / `auth_headers` fixtures for authenticated requests
- `pytest`, `httpx` in `[dependency-groups] dev`

**Run tests:** `cd apps/api && python -m uv run pytest tests/ -v`
