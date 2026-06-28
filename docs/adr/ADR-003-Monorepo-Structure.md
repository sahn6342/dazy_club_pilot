# ADR-003: Monorepo Structure

## Status
Accepted

## Context
The product includes a public website, future admin portal, API, shared UI, shared contracts, and common configuration.

## Decision
Use a monorepo with `apps/web`, `apps/admin`, `apps/api`, `packages/ui`, `packages/shared`, `packages/config`, `infra`, `assets`, and `docs`.

## Alternatives Considered
- Separate repositories per app.
- Single app folder without package boundaries.

## Consequences
- Shared contracts and UI stay close to consuming apps.
- CI can validate the whole product together.
- Repo setup needs workspace tooling.
