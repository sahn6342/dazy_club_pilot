# Migration Strategy

## Tooling
Use EF Core migrations for ASP.NET Core 9.

## Launch Migration Order
1. Venue and sport lookup tables.
2. Court and court configuration tables.
3. Public content tables.
4. Lead and corporate enquiry tables.
5. Audit log table.
6. Seed data migration or seed routine.

## Future Migration Order
1. Customer identity.
2. Booking and booking items.
3. Pricing rules.
4. Payment records.
5. OTP challenges.

## Safety
Every migration must be reversible in non-production environments and reviewed for data loss before production.
