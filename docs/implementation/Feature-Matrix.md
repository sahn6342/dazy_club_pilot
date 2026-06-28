# Feature Matrix

| Feature | Scope | UI | API | DB | Tests |
|---|---|---|---|---|---|
| Home | Launch | Home | sports, gallery, testimonials, notifications | seeded content | smoke, responsive |
| Sports | Launch | Sports, Sport Detail | GET /sports | sports, courts, configurations | API + UI |
| Gallery | Launch | Gallery | GET /gallery | gallery_items | API + UI |
| Testimonials | Launch | Testimonials | GET /testimonials | testimonials | API + UI |
| Contact Enquiry | Launch | Contact | POST /contact-enquiries | leads | validation + persistence |
| Corporate Enquiry | Launch | Corporate Events | POST /corporate-enquiries | corporate_enquiries | validation + persistence |
| Booking | Future | Booking flow | /availability, /bookings | bookings, booking_items | deferred |
| Payment | Future | Payment step | /payments | payments | deferred |
| OTP | Future | OTP screens | /otp/send, /otp/verify | otp_challenges | deferred |
| Admin | Future | Admin shell | admin APIs | audit_logs and content tables | route smoke |
