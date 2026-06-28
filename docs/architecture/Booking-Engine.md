# Booking Engine

## Status
Deferred from first launch.

## Responsibilities
- Query availability.
- Lock selected slots.
- Create bookings with one or more booking items.
- Release inventory on cancellation or lock expiry.
- Enforce booking duration and interval rules.
- Coordinate with pricing, OTP, payment, and notifications.

## Rules
- 15-minute internal intervals.
- 30-minute minimum booking.
- Multiple courts per order.
- Availability check before payment.
- Configurable slot lock timeout.
- Cancellation releases inventory immediately.

## Launch Boundary
Public launch may show booking CTAs but must route them to enquiry/contact.
