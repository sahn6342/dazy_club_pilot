# ADR-005: React Vite Frontend

## Status
Accepted

## Context
The public site and admin shell need fast iteration, strong typing, reusable components, and motion-friendly UI.

## Decision
Use React, Vite, TypeScript, Tailwind, shadcn-style components, and motion for `apps/web` and `apps/admin`.

## Alternatives Considered
- Next.js.
- Plain React without shared packages.
- Server-rendered MVC.

## Consequences
- Public app must be optimized for SEO and performance intentionally.
- Shared UI and config packages should be created early.
