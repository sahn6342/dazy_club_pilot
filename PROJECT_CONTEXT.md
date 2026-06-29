# Dazy.club Project Context

## Product
Dazy.club is a premium sports experience platform. The first launch is a public website that lets visitors understand the venue, browse sports, view gallery/testimonial proof, and submit contact or corporate-event enquiries.

## Launch Scope
- Public browse and enquiry experience only.
- Sports: Cricket, Badminton, Pickleball.
- Screens: Home, Sports, Sport Detail, Gallery, Testimonials, About, Contact, Corporate Events, FAQ.
- Enquiry capture for general visitors and corporate/event organizers.
- Seeded demo content is allowed until final brand copy, media, and testimonials are supplied.

## Deferred Scope
- Live booking checkout.
- OTP/SMS authentication.
- Payment gateway integration.
- Full admin CMS workflows.
- CRM automation.
- Wallet, membership, cafe, and mobile apps.

## Architecture Defaults
- Design first in Figma, then implement.
- Monorepo: apps/web, apps/admin, apps/api, packages/ui, packages/shared, packages/config, infra, assets, docs.
- Frontend: React, Vite, TypeScript, Tailwind, shadcn-style components, motion.
- Backend: FastAPI (Python 3.12) — see ADR-011.
- Database: PostgreSQL.
- Payment and OTP must be designed behind provider adapters even while deferred.

## Working Rule
Read this file, docs/Master-Index.md, docs/Documentation-Map.md, docs/product/PRD.md, and docs/Decision-Log.md before design or code work. Do not invent requirements that conflict with these docs.
