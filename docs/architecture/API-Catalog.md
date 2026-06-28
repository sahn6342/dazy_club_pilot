# API Catalog

## Base
All public API endpoints use `/api/v1`.

## Launch Endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | /api/v1/sports | List supported sports and highlights |
| GET | /api/v1/gallery | List public gallery items |
| GET | /api/v1/testimonials | List public testimonials |
| GET | /api/v1/notifications | List public campaign/banner messages |
| POST | /api/v1/contact-enquiries | Create general enquiry |
| POST | /api/v1/corporate-enquiries | Create corporate/event enquiry |

## Reserved Future Endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | /api/v1/availability | Query available slots |
| POST | /api/v1/bookings | Create booking |
| GET | /api/v1/bookings/{id} | Read booking |
| POST | /api/v1/bookings/{id}/cancel | Cancel booking |
| POST | /api/v1/bookings/{id}/extend | Extend booking |
| POST | /api/v1/payments | Start or record payment |
| POST | /api/v1/otp/send | Send OTP |
| POST | /api/v1/otp/verify | Verify OTP |
