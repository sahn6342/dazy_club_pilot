# ADR-006: PostgreSQL Primary Database

## Status
Accepted

## Context
Dazy.club needs relational modeling for venue, sports, courts, enquiries, future bookings, pricing, payments, and audit logs.

## Decision
Use PostgreSQL as the primary database.

## Alternatives Considered
- SQLite for production.
- Document database.

## Consequences
- EF Core migrations should be used for schema changes.
- Local development should provide PostgreSQL through Docker Compose.
- Indexes and constraints must be documented before implementation.
