# Traceability Matrix

| ID | Requirement | Launch | Screen/API/Entity | Test |
|---|---|---|---|---|
| PRD-001 | Present Dazy.club as a premium sports experience | Launch | Home, About | Visual review, responsive smoke |
| PRD-002 | Let visitors browse Cricket, Badminton, Pickleball | Launch | Sports, Sport Detail, GET /api/v1/sports, Sport | API integration, UI render |
| PRD-003 | Show social proof through gallery and testimonials | Launch | Gallery, Testimonials, GalleryItem, Testimonial | API integration, UI render |
| PRD-004 | Capture general enquiries | Launch | Contact, POST /api/v1/contact-enquiries, Lead | Form validation, API persistence |
| PRD-005 | Capture corporate/event enquiries | Launch | Corporate Events, POST /api/v1/corporate-enquiries, CorporateEnquiry | Form validation, API persistence |
| PRD-006 | Support mobile-first responsive browsing | Launch | All public screens | Responsive E2E |
| PRD-007 | Use seeded demo content until final content exists | Launch | Seed data, CMS-read contracts | Seed verification |
| BK-001 | Allow live booking checkout | Future | Booking flow, Booking, BookingItem | Deferred E2E |
| BK-002 | Enforce 15-minute intervals and 30-minute minimum | Future | Availability, Booking Engine | Unit tests |
| BK-003 | Check availability before payment | Future | GET /availability, POST /bookings | Integration tests |
| PAY-001 | Support payment provider without app rewrite | Future | IPaymentProvider, Payment | Adapter tests |
| OTP-001 | Support OTP provider without app rewrite | Future | IOtpProvider, OtpChallenge | Adapter tests |
| ADM-001 | Provide admin shell and later CMS workflows | Future | Admin app, AuditLog | Route smoke |

## Completion Rule
Every implemented feature must map to at least one requirement, one interface or entity, and one test scenario.
