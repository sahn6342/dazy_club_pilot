from brand import BRAND_NAME
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
        id="sport-football",
        slug="football",
        name="Football",
        tagline="Big-pitch energy on the same premium turf.",
        description="Turf football for friendly matches, team practice, and tournaments, played on the turf shared with cricket.",
        highlights=["Premium turf", "Teams of any size", "Great for friendly matches and events"],
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

# Sports that have no court of their own: they are played on another sport's court. {sport: sport whose court it uses}.
# A booking under either sport takes the same (court, slot), so the other sport sees that slot as taken.
SHARED_COURT_SPORTS: dict[str, str] = {"football": "cricket"}

GALLERY_ITEMS: list[GalleryItemDto] = [
    GalleryItemDto(id="gallery-1", title="Evening turf sessions", sportSlug="cricket", tone="electric",
                   imageUrl="https://images.unsplash.com/photo-1531415074968-036ba1b575da?auto=format&fit=crop&w=800&q=80"),
    GalleryItemDto(id="gallery-2", title="Fast rally corners", sportSlug="badminton", tone="focused",
                   imageUrl="https://images.unsplash.com/photo-1626224583764-f87db24ac4ea?auto=format&fit=crop&w=800&q=80"),
    GalleryItemDto(id="gallery-3", title="Weekend social play", sportSlug="pickleball", tone="playful",
                   imageUrl="https://images.unsplash.com/photo-1612872087720-bb876e2e67d1?auto=format&fit=crop&w=800&q=80"),
]

TESTIMONIALS: list[TestimonialDto] = [
    # Placeholder testimonials (replaced by the real Google reviews below):
    # TestimonialDto(
    #     id="testimonial-1",
    #     name="Priya R.",
    #     context="Weekend player",
    #     quote="A polished sports venue that feels made for weekend plans and team energy.",
    # ),
    # TestimonialDto(
    #     id="testimonial-2",
    #     name="Arjun M.",
    #     context="Corporate organizer",
    #     quote="The enquiry flow makes it simple to start planning a team sports day.",
    # ),
    # Real Google reviews (5 stars), shown as first name + initial.
    TestimonialDto(id="google-1", name="Sanraj S.", context="Google review",
                   quote="Well-planned sports facility with cricket, football and pickleball options. Great to have a place like this nearby!"),
    TestimonialDto(id="google-2", name="Lucky R.", context="Google review",
                   quote="Visited DAZY CLUB recently and really liked the setup. The size of the turf definitely stands out."),
    TestimonialDto(id="google-3", name="Shivam S.", context="Google Local Guide",
                   quote="A fantastic place for sports enthusiasts. Great concept, spacious turf, and plenty of reasons to come back. The turf is seriously spacious!"),
    TestimonialDto(id="google-4", name="Ashish P.", context="Google Local Guide",
                   quote="Best"),
    TestimonialDto(id="google-5", name="Rudra S.", context="Google review",
                   quote="Finally, a large football turf near Saguna More! Plenty of room to enjoy the game. DAZY CLUB is definitely worth checking out."),
    TestimonialDto(id="google-6", name="Yash R.", context="Google Local Guide",
                   quote="A fantastic place for sports enthusiasts. Great concept, spacious turf, and plenty of reasons to come back."),
    TestimonialDto(id="google-7", name="Ritik R.", context="Google review",
                   quote="The turf is seriously spacious! One of the biggest I've seen around Patna. Great place to play with friends."),
    TestimonialDto(id="google-8", name="Kumar A.", context="Google review",
                   quote="Really nice cricket practice nets and a great setup for anyone who enjoys playing cricket. Had a good time!"),
]

NOTIFICATIONS: list[NotificationDto] = [
    NotificationDto(
        id="launch-banner",
        title="Now open",
        body=f"Browse sports, check availability, and book your court at {BRAND_NAME}.",
        surface="banner",
    ),
]

# Slots are no longer a static list — they are generated from schedule data
# (ScheduleRule/ScheduleException) per court in services/availability_service.py.
