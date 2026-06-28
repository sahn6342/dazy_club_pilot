# Database Schema

## Database
PostgreSQL is the primary database.

## Launch Tables
- venues
- sports
- courts
- court_configurations
- leads
- corporate_enquiries
- gallery_items
- testimonials
- notifications
- audit_logs

## Future Tables
- customers
- bookings
- booking_items
- pricing_rules
- payments
- otp_challenges

## Rule
Launch migrations may include future-ready tables only if they do not expose live booking/payment/OTP behavior.
