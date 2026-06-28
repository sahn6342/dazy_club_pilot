# Authentication Strategy

## Launch
No visitor authentication is required for browse and enquiry. Public form submissions must use validation, rate limiting when implemented, and bot protection if needed.

## Future Booking
Guest identity is verified by OTP before booking confirmation. OTP provider selection is deferred behind an adapter.

## Future Admin
Admin portal uses role-based access control. Initial roles: Admin, Content Manager, Operations. Sensitive actions must write audit logs.
