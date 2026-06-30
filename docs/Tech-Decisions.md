# Tech Decisions

## Actual stack (as implemented)

| Concern | Choice | Notes |
|---|---|---|
| Frontend | React 18 + Vite + TypeScript | react-router-dom v7, plain CSS |
| Backend | FastAPI (Python 3.12) | Pydantic v2, uvicorn, uv package manager |
| Database | SQLite (pilot) | SQLAlchemy 2.0 sync, Alembic migrations |
| Auth | JWT HS256 (pyjwt) | 8h expiry, bcrypt passwords |
| Monorepo | pnpm workspaces | shared `@dazy/shared` types package |
| Testing | pytest + Playwright | 278 backend tests, E2E web + admin |
| Styling | Plain CSS + CSS variables | Dark theme, gold accent `#d8b456` |

## Deferred

| Concern | Plan |
|---|---|
| Production DB | PostgreSQL — swap `DAZY_DB_URL`, zero code changes |
| Payment | Adapter pattern ready; provider TBD |
| OTP / SMS | Adapter pattern ready; provider TBD |
| Redis | Slot locking for high concurrency (SQLite partial-index sufficient for pilot) |
| CDN / media | File upload stored locally at `/media/gallery/`; swap to S3 path when ready |
| Notifications | Email/SMS confirmation flow (currently booking ref shown on screen only) |
