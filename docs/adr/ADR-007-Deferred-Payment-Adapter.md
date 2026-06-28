# ADR-007: Deferred Payment Provider Adapter

## Status
Accepted

## Context
Payment is not part of the first launch. The app still needs future payment support without rewriting booking and checkout contracts.

## Decision
Do not select or integrate a live payment provider for launch. Define payment contracts, statuses, and a backend provider adapter boundary for future implementation.

## Alternatives Considered
- Integrate Razorpay immediately.
- Integrate Stripe immediately.
- Hardcode a fake payment path into the product flow.

## Consequences
- First launch cannot collect payments.
- Future provider integration can be added behind the adapter.
- Payment UI must be marked as future/deferred in Figma.
