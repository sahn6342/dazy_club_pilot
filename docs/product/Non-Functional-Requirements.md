# Non-Functional Requirements

## Performance
- Lighthouse target: greater than 95.
- Public pages should render quickly on mobile networks.
- Image assets must be optimized and lazy-loaded where appropriate.

## Accessibility
- Target WCAG AA.
- Maintain high contrast in dark-first theme.
- Keyboard navigation must work for navigation and forms.
- Form errors must be visible and screen-reader understandable.

## Reliability
- Enquiry submission failures must show recoverable error states.
- Seeded content must allow the public site to run before CMS is complete.

## Security
- Validate and sanitize all enquiry input.
- Do not expose secrets in frontend apps.
- Rate-limit public form submissions when implemented.

## Maintainability
- Shared UI components and tokens must live in reusable packages after implementation.
- Payment and OTP must remain provider-agnostic until providers are selected.
