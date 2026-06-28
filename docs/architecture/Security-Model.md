# Security Model

## Launch
- Validate all public enquiry input.
- Sanitize stored text fields before rendering.
- Keep secrets out of frontend apps.
- Use HTTPS in deployed environments.
- Add rate limiting and spam protection before production traffic.

## Future
- OTP provider integration behind adapter.
- Payment provider integration behind adapter.
- Admin RBAC.
- Audit logs for admin writes and booking overrides.

## Data Protection
Collect only needed enquiry fields. Treat phone, email, and corporate details as sensitive operational data.
