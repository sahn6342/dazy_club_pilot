# Testing Strategy

## Pyramid
Unit > Integration > E2E.

## Launch Tests
- Unit tests for validation helpers and shared utilities.
- API integration tests for sports, gallery, testimonials, notifications, contact enquiry, and corporate enquiry.
- Frontend tests for public screens and form validation.
- E2E smoke for Home, Sports, Gallery, Testimonials, Contact, Corporate Events, and mobile navigation.

## Future Tests
- Booking interval and duration rules.
- Slot conflict detection.
- Slot lock expiry.
- Payment failure recovery.
- OTP expiry and retry behavior.

## Quality Gates
- Build passes.
- Lint passes.
- Typecheck passes.
- Tests pass.
- Lighthouse target greater than 95.
- Accessibility AA target.
