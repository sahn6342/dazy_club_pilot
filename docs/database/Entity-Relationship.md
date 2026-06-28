# Entity Relationship

## Launch Relationships
- Venue has many Courts.
- Sport maps to Courts through CourtConfiguration.
- GalleryItem may reference Sport.
- Testimonial may reference Sport.
- Lead may reference interested Sport.
- CorporateEnquiry may reference preferred Sport.
- Notification may target public surfaces.

## Future Relationships
- Customer has many Bookings.
- Booking has many BookingItems.
- BookingItem references Court and Sport.
- PricingRule may reference Sport, Court, date, slot, or event context.
- Payment references Booking.
- OtpChallenge references Customer or pending guest identity.

## Core Chain
Venue -> Court -> CourtConfiguration -> Sport

Customer -> Booking -> BookingItem -> Court
