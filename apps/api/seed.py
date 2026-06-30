from models import SportDto, GalleryItemDto, TestimonialDto, NotificationDto

SPORTS: list[SportDto] = [
    SportDto(
        id="sport-cricket",
        slug="cricket",
        name="Cricket",
        tagline="Premium turf energy for groups and events.",
        description="A high-energy cricket experience for weekend games, friendly rivalries, and corporate tournaments.",
        highlights=["Group-friendly turf", "Evening game energy", "Ideal for corporate tournaments"],
    ),
    SportDto(
        id="sport-badminton",
        slug="badminton",
        name="Badminton",
        tagline="Fast rallies with flexible court configuration.",
        description="A crisp, social badminton experience designed around flexible play and great for all skill levels.",
        highlights=["Fast-paced sessions", "Multiple court layouts", "Great for families and friends"],
    ),
    SportDto(
        id="sport-pickleball",
        slug="pickleball",
        name="Pickleball",
        tagline="Playful, modern, and easy to start.",
        description="A welcoming sport for teams, first-timers, and social groups who want something fresh and energetic.",
        highlights=["Beginner friendly", "Social format", "Event-ready experience"],
    ),
]

GALLERY_ITEMS: list[GalleryItemDto] = [
    GalleryItemDto(id="gallery-1", title="Evening turf sessions", sportSlug="cricket", tone="electric",
                   imageUrl="https://images.unsplash.com/photo-1531415074968-036ba1b575da?auto=format&fit=crop&w=800&q=80"),
    GalleryItemDto(id="gallery-2", title="Fast rally corners", sportSlug="badminton", tone="focused",
                   imageUrl="https://images.unsplash.com/photo-1626224583764-f87db24ac4ea?auto=format&fit=crop&w=800&q=80"),
    GalleryItemDto(id="gallery-3", title="Weekend social play", sportSlug="pickleball", tone="playful",
                   imageUrl="https://images.unsplash.com/photo-1612872087720-bb876e2e67d1?auto=format&fit=crop&w=800&q=80"),
]

TESTIMONIALS: list[TestimonialDto] = [
    TestimonialDto(
        id="testimonial-1",
        name="Priya R.",
        context="Weekend player",
        quote="A polished sports venue that feels made for weekend plans and team energy.",
    ),
    TestimonialDto(
        id="testimonial-2",
        name="Arjun M.",
        context="Corporate organizer",
        quote="The enquiry flow makes it simple to start planning a team sports day.",
    ),
]

NOTIFICATIONS: list[NotificationDto] = [
    NotificationDto(
        id="launch-banner",
        title="Now open",
        body="Browse sports, check availability, and book your court at Dazy.club.",
        surface="banner",
    ),
]

# Slots are no longer a static list — they are generated from schedule data
# (ScheduleRule/ScheduleException) per court in services/availability_service.py.
