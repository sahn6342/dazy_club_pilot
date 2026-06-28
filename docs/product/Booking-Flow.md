# Booking Flow

## Status
Deferred from first launch. Design and contracts should prepare for this flow, but public launch must not enable live booking.

## Future Flow
1. Select sport.
2. Select date and time.
3. View available courts/configurations.
4. Select one or more slots/courts.
5. Verify guest identity through OTP.
6. Lock selected inventory.
7. Review booking.
8. Choose full payment, partial payment, or pay at venue.
9. Confirm booking.
10. Send notification.

## Rules
- Minimum booking duration is 30 minutes.
- Internal interval is 15 minutes.
- Multiple courts can be booked in one order.
- Availability is checked before payment.
- Slot lock timeout is configurable.
- Cancelled bookings immediately release inventory.
- Admin override is future admin scope and must create audit logs.
