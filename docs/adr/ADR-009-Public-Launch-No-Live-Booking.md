# ADR-009: Public Launch Without Live Booking

## Status
Accepted

## Context
The user wants to land first, then add payment and OTP in a later phase. Live booking depends on availability, locking, OTP, and payment decisions.

## Decision
The first launch is browse + enquiry only. Booking CTAs route to enquiry/contact until live booking is implemented.

## Alternatives Considered
- Ship live booking with stub payment and OTP.
- Ship public content only with no enquiry capture.

## Consequences
- Launch can happen earlier with less operational risk.
- Figma and docs still preserve future booking flow.
- No fake booking confirmation should be shown to real users.
