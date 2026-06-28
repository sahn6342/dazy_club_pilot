# Booking State Machine

## States
Draft
→ Slot Selected
→ Slot Locked
→ Payment Pending
→ Confirmed
→ Completed
→ Cancelled
→ Expired
→ Refunded

## Rules
BSM-001 Slot lock expires after configurable timeout.
BSM-002 Only Confirmed bookings reserve inventory.
BSM-003 Cancelled/Expired bookings release slots immediately.
