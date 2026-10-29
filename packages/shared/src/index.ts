export const BRAND = {
  name: "Dazy Club",
  adminTitle: "Admin",
  tagline: "Cricket · Football · Badminton · Pickleball",
} as const;

export type LaunchScope = "launch" | "future" | "excluded";

export type Sport = {
  id: string;
  slug: "cricket" | "football" | "badminton" | "pickleball";
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
  /** Picks the placeholder avatar (reviewers have no photo). Defaults to male. */
  gender?: "male" | "female";
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
    id: "sport-football",
    slug: "football",
    name: "Football",
    tagline: "Big-pitch energy on the same premium turf.",
    description:
      "Turf football for friendly matches, team practice, and tournaments, played on the turf shared with cricket.",
    highlights: ["Premium turf", "Teams of any size", "Great for friendly matches and events"]
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
  // Placeholder testimonials (replaced by the real Google reviews below):
  // {
  //   id: "testimonial-1",
  //   name: "Priya R.",
  //   context: "Weekend player",
  //   quote: "A polished sports venue that feels made for weekend plans and team energy."
  // },
  // {
  //   id: "testimonial-2",
  //   name: "Arjun M.",
  //   context: "Corporate organizer",
  //   quote: "The enquiry flow makes it simple to start planning a team sports day."
  // },
  // Real Google reviews (5 stars), shown as first name + initial.
  {
    id: "google-1",
    name: "Sanraj S.",
    context: "Google review",
    quote: "Well-planned sports facility with cricket, football and pickleball options. Great to have a place like this nearby!",
    gender: "male"
  },
  {
    id: "google-2",
    name: "Lucky R.",
    context: "Google review",
    quote: "Visited DAZY CLUB recently and really liked the setup. The size of the turf definitely stands out.",
    gender: "male"
  },
  {
    id: "google-3",
    name: "Shivam S.",
    context: "Google Local Guide",
    quote: "A fantastic place for sports enthusiasts. Great concept, spacious turf, and plenty of reasons to come back. The turf is seriously spacious!",
    gender: "male"
  },
  {
    id: "google-4",
    name: "Ashish P.",
    context: "Google Local Guide",
    quote: "Best",
    gender: "male"
  },
  {
    id: "google-5",
    name: "Rudra S.",
    context: "Google review",
    quote: "Finally, a large football turf near Saguna More! Plenty of room to enjoy the game. DAZY CLUB is definitely worth checking out.",
    gender: "male"
  },
  {
    id: "google-6",
    name: "Yash R.",
    context: "Google Local Guide",
    quote: "A fantastic place for sports enthusiasts. Great concept, spacious turf, and plenty of reasons to come back.",
    gender: "male"
  },
  {
    id: "google-7",
    name: "Ritik R.",
    context: "Google review",
    quote: "The turf is seriously spacious! One of the biggest I've seen around Patna. Great place to play with friends.",
    gender: "male"
  },
  {
    id: "google-8",
    name: "Kumar A.",
    context: "Google review",
    quote: "Really nice cricket practice nets and a great setup for anyone who enjoys playing cricket. Had a good time!",
    gender: "male"
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
  courtId?: string | null;
  courtName?: string | null;
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

export { warmUpApi, fetchWithWake, networkMessage } from "./wake";
