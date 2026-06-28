# Index Strategy

## Launch
- sports.slug unique index.
- gallery_items.status index.
- testimonials.status index.
- notifications.status index.
- leads.created_at index.
- corporate_enquiries.created_at index.

## Future
- bookings.customer_id index.
- booking_items.court_id, start_at, end_at composite index.
- booking_items.status index.
- pricing_rules.sport_id index.
- payments.booking_id index.
- otp_challenges.phone_or_email index.

## Rule
Add indexes with migrations and verify query plans for hot paths before launch traffic.
