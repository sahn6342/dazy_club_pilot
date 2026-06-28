# Frontend Architecture

## Apps
- `apps/web`: launch public website.
- `apps/admin`: future admin portal shell.

## Stack
- React.
- Vite.
- TypeScript strict.
- Tailwind.
- shadcn-style reusable components.
- Motion for purposeful interactions.

## Public App Structure
- Routes for Home, Sports, Sport Detail, Gallery, Testimonials, About, Contact, Corporate Events, FAQ.
- Data access through typed API client contracts from `packages/shared`.
- UI primitives from `packages/ui`.
- Seeded content can be rendered through API-backed or local fallback data during early implementation.

## Launch Constraint
Booking CTAs must route to enquiry/contact until live booking is approved.
