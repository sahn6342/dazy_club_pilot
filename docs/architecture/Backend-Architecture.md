# Backend Architecture

## Stack
- ASP.NET Core 9 / .NET 9.
- Modular monolith.
- Clean Architecture with vertical slices where useful.
- EF Core with PostgreSQL.

## Launch Modules
- Public Content.
- Sports.
- Gallery.
- Testimonials.
- Notifications.
- Leads.
- Corporate Enquiries.
- Audit foundation.

## Deferred Modules
- Availability.
- Booking.
- Pricing.
- Payment.
- OTP/Auth.
- CRM automation.
- CMS workflows.

## Cross-Cutting
- OpenAPI.
- Validation pipeline.
- Central exception handling.
- Structured logging.
- CORS for web/admin apps.
- Environment-based configuration.
