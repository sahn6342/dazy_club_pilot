namespace Dazy.Api;

public static class SeedData
{
    public static readonly SportDto[] Sports =
    [
        new(
            "sport-cricket",
            "cricket",
            "Cricket",
            "Premium turf energy for groups and events.",
            "A high-energy cricket experience for weekend games, friendly rivalries, and corporate tournaments.",
            ["Group-friendly turf", "Evening game energy", "Future multi-slot booking ready"]),
        new(
            "sport-badminton",
            "badminton",
            "Badminton",
            "Fast rallies with flexible court configuration.",
            "A crisp, social badminton experience designed around flexible play and future availability-aware booking.",
            ["Fast sessions", "Configuration-aware courts", "Great for families and friends"]),
        new(
            "sport-pickleball",
            "pickleball",
            "Pickleball",
            "Playful, modern, and easy to start.",
            "A welcoming sport for teams, first-timers, and social groups who want something fresh and energetic.",
            ["Beginner friendly", "Social format", "Event-ready experience"])
    ];

    public static readonly GalleryItemDto[] GalleryItems =
    [
        new("gallery-1", "Evening turf sessions", "cricket", "electric"),
        new("gallery-2", "Fast rally corners", "badminton", "focused"),
        new("gallery-3", "Weekend social play", "pickleball", "playful")
    ];

    public static readonly TestimonialDto[] Testimonials =
    [
        new("testimonial-1", "Seed testimonial", "Weekend player", "A polished sports venue that feels made for weekend plans and team energy."),
        new("testimonial-2", "Seed testimonial", "Corporate organizer", "The enquiry flow makes it simple to start planning a team sports day.")
    ];

    public static readonly NotificationDto[] Notifications =
    [
        new("launch-banner", "First launch", "Browse sports and enquire now. Live booking, OTP, and payment are coming next.", "banner")
    ];
}
