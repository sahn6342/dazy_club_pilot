# ADR-011: Replace ASP.NET Core 9 with FastAPI

**Status:** Accepted  
**Date:** 2026-06-28  
**Supersedes:** ADR-004 (Backend .NET 9)

## Context

The pilot backend has 7 endpoints serving static seed data (no database, no auth). ASP.NET Core 9 is production-capable but disproportionately heavy for this stage:

- ~400MB Docker image (runtime + SDK layers)
- ~1–3s cold start on serverless/container-per-request hosts
- C# ecosystem adds friction for rapid iteration on a small team
- No benefit from .NET's strength (EF Core, SignalR) until DB/auth phases

## Decision

Replace `apps/api/` with **FastAPI** (Python 3.12, Pydantic v2, uvicorn).

- Same 7 endpoints, identical request/response contracts
- Pydantic v2 handles validation — 422 responses automatic on bad input
- GZip middleware added (1 line)
- Cache-Control headers on all static GET endpoints
- Auto OpenAPI docs at `/docs` and `/redoc`
- Package management via **uv** (fastest Python resolver, lockfile-based)

## Consequences

**Benefits:**
- Docker image ~60MB (python:3.12-alpine) vs ~400MB
- Sub-100ms cold start
- `/docs` Swagger UI replaces manual API documentation
- Python aligns with future ML/data features (e.g. recommendation engine)
- Faster local iteration: `--reload` hot-reload, no compile step

**Trade-offs:**
- Python async ecosystem (asyncpg, SQLAlchemy async) required when DB is integrated
- Type safety relies on Pydantic + mypy vs C# compile-time guarantees
- Team must be comfortable with Python

## Migration Path

When database integration begins (Phase 2):
- Add `asyncpg` + `SQLAlchemy[asyncio]` to pyproject.toml
- Replace seed data with async DB queries
- Use Alembic for migrations (equivalent to EF Core migrations)
