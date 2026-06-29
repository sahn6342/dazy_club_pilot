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
    highlights: ["Group-friendly turf", "Evening game energy", "Ideal for corporate tournaments"]
  },
  {
    id: "sport-badminton",
    slug: "badminton",
    name: "Badminton",
    tagline: "Fast rallies with flexible court configuration.",
    description:
      "A crisp, social badminton experience designed around flexible play and great for all skill levels.",
    highlights: ["Fast-paced sessions", "Multiple court layouts", "Great for families and friends"]
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
    name: "Priya R.",
    context: "Weekend player",
    quote: "A polished sports venue that feels made for weekend plans and team energy."
  },
  {
    id: "testimonial-2",
    name: "Arjun M.",
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

export type Slot = {
  id: string;
  sportSlug: string;
  date: string;
  startTime: string;
  endTime: string;
  available: boolean;
  maxPlayers: number;
  price?: number | null;
  discountPercent?: number | null;
  finalPrice?: number | null;
};

export type BookingEnquiry = {
  name: string;
  contact: string;
  slotId: string;
  sportSlug: string;
  date: string;
  startTime: string;
  players: number;
  promoCode?: string;
  message?: string;
};
