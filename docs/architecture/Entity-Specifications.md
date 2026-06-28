# Entity Specifications

## Venue
- id: UUID
- name
- slug
- address
- timezone
- status

## Sport
- id: UUID
- name
- slug
- description
- hero_media
- status

## Court
- id: UUID
- venue_id
- name
- type
- configuration_mode
- status

## CourtConfiguration
- id: UUID
- court_id
- sport_id
- capacity
- notes

## Lead
- id: UUID
- name
- phone
- email
- interested_sport_id
- message
- source
- status
- created_at

## CorporateEnquiry
- id: UUID
- contact_name
- company
- phone
- email
- event_type
- estimated_group_size
- preferred_date
- preferred_sport_id
- message
- status
- created_at

## GalleryItem
- id: UUID
- title
- media_url
- media_type
- sport_id
- status
- sort_order

## Testimonial
- id: UUID
- name
- role_or_context
- quote
- rating
- sport_id
- status

## Notification
- id: UUID
- title
- body
- surface
- status
- starts_at
- ends_at

## AuditLog
- id: UUID
- actor_id
- action
- entity_type
- entity_id
- metadata
- created_at

## Future Booking
Booking stores booking header. BookingItem stores court allocations. PricingRule stores dynamic pricing rules. Payment stores provider-agnostic payment state. OtpChallenge stores provider-agnostic verification state.
