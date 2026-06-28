export type LaunchScope = "launch" | "future" | "excluded";

export type Sport = {
  id: string;
  slug: "cricket" | "badminton" | "pickleball";
  name: string;
  tagline: string;
  description: string;
  highlights: string[];
};

export type GalleryItem = {
  id: string;
  title: string;
  sportSlug: Sport["slug"];
  tone: string;
};

export type Testimonial = {
  id: string;
  name: string;
  context: string;
  quote: string;
};

export type Notification = {
  id: string;
  title: string;
  body: string;
  surface: "banner" | "toast" | "modal";
};

export type ContactEnquiry = {
  name: string;
  contact: string;
  interestedSport?: string;
  message: string;
};

export type CorporateEnquiry = {
  contactName: string;
  company: string;
  contact: string;
  eventType: string;
  estimatedGroupSize?: number;
  preferredDate?: string;
  preferredSport?: string;
  message: string;
};

export const launchSports: Sport[] = [
  {
    id: "sport-cricket",
    slug: "cricket",
    name: "Cricket",
    tagline: "Premium turf energy for groups and events.",
    description:
      "A high-energy cricket experience for weekend games, friendly rivalries, and corporate tournaments.",
    highlights: ["Group-friendly turf", "Evening game energy", "Future multi-slot booking ready"]
  },
  {
    id: "sport-badminton",
    slug: "badminton",
    name: "Badminton",
    tagline: "Fast rallies with flexible court configuration.",
    description:
      "A crisp, social badminton experience designed around flexible play and future availability-aware booking.",
    highlights: ["Fast sessions", "Configuration-aware courts", "Great for families and friends"]
  },
  {
    id: "sport-pickleball",
    slug: "pickleball",
    name: "Pickleball",
    tagline: "Playful, modern, and easy to start.",
    description:
      "A welcoming sport for teams, first-timers, and social groups who want something fresh and energetic.",
    highlights: ["Beginner friendly", "Social format", "Event-ready experience"]
  }
];

export const galleryItems: GalleryItem[] = [
  { id: "gallery-1", title: "Evening turf sessions", sportSlug: "cricket", tone: "electric" },
  { id: "gallery-2", title: "Fast rally corners", sportSlug: "badminton", tone: "focused" },
  { id: "gallery-3", title: "Weekend social play", sportSlug: "pickleball", tone: "playful" }
];

export const testimonials: Testimonial[] = [
  {
    id: "testimonial-1",
    name: "Seed testimonial",
    context: "Weekend player",
    quote: "A polished sports venue that feels made for weekend plans and team energy."
  },
  {
    id: "testimonial-2",
    name: "Seed testimonial",
    context: "Corporate organizer",
    quote: "The enquiry flow makes it simple to start planning a team sports day."
  }
];

export const notifications: Notification[] = [
  {
    id: "launch-banner",
    title: "First launch",
    body: "Browse sports and enquire now. Live booking, OTP, and payment are coming next.",
    surface: "banner"
  }
];

export const futureCapabilities = [
  "Live availability",
  "Guest OTP",
  "Booking checkout",
  "Payment provider adapter",
  "Admin CMS workflows",
  "CRM automation"
] as const;
