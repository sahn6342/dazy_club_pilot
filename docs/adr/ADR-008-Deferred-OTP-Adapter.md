# ADR-008: Deferred OTP Provider Adapter

## Status
Accepted

## Context
OTP is needed for future guest booking but not for the first browse-and-enquiry launch.

## Decision
Do not select or integrate a live OTP/SMS provider for launch. Define OTP contracts and a backend provider adapter boundary for future implementation.

## Alternatives Considered
- Integrate Twilio immediately.
- Integrate MSG91 immediately.
- Couple OTP directly to booking code.

## Consequences
- First launch has no live OTP dependency.
- Future OTP provider can be selected later.
- Booking contracts can reference OTP without hardcoding the provider.
