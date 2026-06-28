# ADR-002: Figma-First Workflow

## Status
Accepted

## Context
Dazy.club needs a premium, dark-first public experience. The visual direction, responsive behavior, and future booking states should be aligned before code.

## Decision
Create a Figma design file named `Dazy.club - Landing Experience` before implementation. Figma must include foundations, components, public screens, responsive frames, deferred future-booking states, admin shell preview, and handoff notes.

## Alternatives Considered
- Build the UI first and polish later.
- Create wireframes only.

## Consequences
- Code implementation waits for design approval.
- Frontend build can map directly to tokens and components.
- Deferred booking, payment, and OTP can be planned visually without shipping them.
