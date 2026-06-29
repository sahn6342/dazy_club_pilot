# ADR-004: ASP.NET Core 9 Backend

## Status
Superseded by ADR-011 (2026-06-28)

## Context
The generated docs selected ASP.NET Core and the user confirmed .NET 9 should remain the backend target.

## Decision
Use ASP.NET Core 9 / .NET 9 for `apps/api`, organized as a modular monolith with Clean Architecture and vertical-slice patterns where useful.

## Alternatives Considered
- Use locally installed .NET 10.
- Use Node.js for the API.

## Consequences
- Local machines must install .NET 9 SDK for implementation.
- Backend can evolve toward services later without starting as distributed complexity.
