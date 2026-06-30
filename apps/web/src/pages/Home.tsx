import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { galleryItems, launchSports, testimonials } from "@dazy/shared";
import { getGallery, resolveImg, type GalleryItem } from "../lib/api";

const AVATAR: Record<string, string> = {
  "testimonial-1": "priya",
  "testimonial-2": "arjun",
};

function usePerView(desktop: number): number {
  const calc = () => {
    if (typeof window === "undefined") return desktop;
    if (window.innerWidth < 720) return 1;
    if (window.innerWidth < 1024) return Math.min(2, desktop);
    return desktop;
  };
  const [pv, setPv] = useState(calc);
  useEffect(() => {
    const h = () => setPv(calc());
    window.addEventListener("resize", h);
    return () => window.removeEventListener("resize", h);
  }, []);
  return pv;
}

function Carousel<T extends object>({
  items,
  perView,
  autoMs = 4200,
  renderItem,
  className = "",
}: {
  items: T[];
  perView: number;
  autoMs?: number;
  renderItem: (item: T, idx: number) => JSX.Element | null;
  className?: string;
}) {
  const pages = Math.ceil(items.length / perView);
  const [page, setPage] = useState(0);

  // Reset when perView changes (resize)
  useEffect(() => { setPage(0); }, [perView]);

  // Auto-advance — simple modulo, no clone needed with crossfade
  useEffect(() => {
    if (pages <= 1) return;
    const t = setInterval(() => setPage((p) => (p + 1) % pages), autoMs);
    return () => clearInterval(t);
  }, [pages, autoMs]);

  return (
    <div className={`carousel ${className}`}>
      <div className="carousel-track">
        {Array.from({ length: pages }, (_, pi) => (
          <div
            key={pi}
            className={`carousel-page${pi === page ? " active" : ""}`}
            style={{ gridTemplateColumns: `repeat(${perView}, 1fr)` }}
            aria-hidden={pi !== page}
          >
            {Array.from({ length: perView }, (_, k) => {
              const idx = (pi * perView + k) % items.length;
              return (
                <div key={k} className="carousel-slide">
                  {renderItem(items[idx], idx)}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      {pages > 1 && (
        <div className="carousel-dots">
          {Array.from({ length: pages }, (_, i) => (
            <button
              key={i}
              className={`carousel-dot${page === i ? " active" : ""}`}
              onClick={() => setPage(i)}
              aria-label={`Slide ${i + 1}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function Home() {
  const [gallery, setGallery] = useState<GalleryItem[]>(galleryItems as GalleryItem[]);
  useEffect(() => {
    getGallery().then((items) => { if (items.length) setGallery(items); }).catch(() => {});
  }, []);

  const galleryPerView = usePerView(3);
  const testimonialPerView = usePerView(2);

  return (
    <>
      <section id="home" className="hero">
        <video
          className="hero-video"
          autoPlay
          muted
          loop
          playsInline
          poster="/images/hero.jpg"
        >
          <source src="/images/hero.mp4" type="video/mp4" />
        </video>
        <div className="hero-overlay" aria-hidden="true" />
        <div className="hero-content">
          <p className="eyebrow">Cricket · Badminton · Pickleball</p>
          <h1>Premium sports energy, built for your next game.</h1>
          <p className="hero-copy">
            Dazy.club brings together Cricket, Badminton, and Pickleball in one premium venue.
            Whether it's a casual weekend game or a corporate event, we've got your court.
          </p>
          <div className="actions">
            <Link className="button primary" to="/book">Book a court</Link>
            <a className="button secondary" href="#sports">View sports</a>
          </div>
        </div>
      </section>

      <section className="stats-band">
        <div className="stats-inner">
          {[
            { value: "3", label: "Sports" },
            { value: "12", label: "Slots / day" },
            { value: "7", label: "Days ahead" },
            { value: "11", label: "Max players" },
          ].map((s) => (
            <div className="stat" key={s.label}>
              <span className="stat-value">{s.value}</span>
              <span className="stat-label">{s.label}</span>
            </div>
          ))}
        </div>
      </section>

      <section id="sports" className="section">
        <div className="section-heading">
          <p className="eyebrow">Sports</p>
          <h2>Choose your court energy.</h2>
          <p>Three sports, one venue. Find your game.</p>
        </div>
        <div className="card-grid">
          {launchSports.map((sport) => (
            <article className="card sport-card" key={sport.id}>
              <div className="card-media">
                <img src={`/images/${sport.slug}.jpg`} alt={`${sport.name} at Dazy.club`} loading="lazy" />
              </div>
              <p className="eyebrow">{sport.name}</p>
              <h3>{sport.tagline}</h3>
              <p>{sport.description}</p>
              <ul>
                {sport.highlights.map((h) => (
                  <li key={h}>{h}</li>
                ))}
              </ul>
              <div className="card-actions">
                <Link className="button primary small" to={`/book?sport=${sport.slug}`}>
                  Book {sport.name}
                </Link>
                <Link className="text-link" to="/contact">Enquire</Link>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section id="how" className="section">
        <div className="section-heading">
          <p className="eyebrow">How it works</p>
          <h2>Booked in three steps.</h2>
          <p>No calls, no waiting. Pick, choose, play.</p>
        </div>
        <div className="card-grid steps">
          {[
            { n: "1", t: "Pick your sport", d: "Cricket, Badminton, or Pickleball — choose the game you're in the mood for." },
            { n: "2", t: "Choose a slot", d: "See live availability for the next 7 days and lock the time that suits you." },
            { n: "3", t: "Play", d: "Get an instant booking reference. Show up, team up, and play." },
          ].map((step) => (
            <article className="card step-card" key={step.n}>
              <span className="step-num">{step.n}</span>
              <h3>{step.t}</h3>
              <p>{step.d}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="action" className="section">
        <div className="section-heading">
          <p className="eyebrow">In action</p>
          <h2>Feel the game before you arrive.</h2>
          <p>Real energy, real rallies — this is the vibe on court.</p>
        </div>
        <div className="action-grid">
          <figure className="action-tile">
            <img src="/images/play-badminton.gif" alt="Badminton rally in action" loading="lazy" />
            <figcaption>Fast badminton rallies</figcaption>
          </figure>
          <figure className="action-tile">
            <img src="/images/play-cricket.gif" alt="Cricket batting on turf" loading="lazy" />
            <figcaption>Skill on the turf</figcaption>
          </figure>
          <figure className="action-tile">
            <img src="/images/play-badminton2.gif" alt="Smash and net play" loading="lazy" />
            <figcaption>Smashes &amp; net play</figcaption>
          </figure>
        </div>
      </section>

      <section id="gallery" className="section">
        <div className="section-heading">
          <p className="eyebrow">Gallery</p>
          <h2>Moments at Dazy.club.</h2>
          <p>A glimpse of the energy, atmosphere, and play you can expect on court.</p>
        </div>
        <Carousel
          items={gallery}
          perView={galleryPerView}
          autoMs={4000}
          className="gallery-carousel"
          renderItem={(item) => {
            const src = resolveImg(item.imageUrl) || `/images/gallery-${item.sportSlug}.jpg`;
            return (
              <figure className="gallery-item">
                <img src={src} alt={item.title} loading="lazy" />
                <figcaption>{item.title}</figcaption>
              </figure>
            );
          }}
        />
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">Testimonials</p>
          <h2>What players say.</h2>
        </div>
        <Carousel
          items={testimonials}
          perView={testimonialPerView}
          autoMs={5500}
          className="testimonial-carousel"
          renderItem={(item) => (
            <article className="card testimonial-card">
              <div className="stars" aria-label="5 out of 5 stars">★★★★★</div>
              <p className="quote">"{item.quote}"</p>
              <div className="testimonial-author">
                <img
                  className="avatar"
                  src={`/images/avatar-${AVATAR[item.id] ?? "priya"}.jpg`}
                  alt={item.name}
                  loading="lazy"
                />
                <p className="byline">{item.name} — {item.context}</p>
              </div>
            </article>
          )}
        />
      </section>

      <section className="section">
        <div className="corporate-band">
          <div className="corporate-copy">
            <p className="eyebrow">Corporate events</p>
            <h2>Plan team outings, tournaments, and private sports days.</h2>
            <p>From small team outings to large corporate tournaments, we handle the court. You bring the energy.</p>
            <div className="actions">
              <Link className="button primary" to="/contact?tab=corporate">Plan an event</Link>
              <Link className="button secondary" to="/book">Book a court</Link>
            </div>
          </div>
          <div className="corporate-image" aria-hidden="true" />
        </div>
      </section>

      <section className="section faq">
        <div className="section-heading">
          <p className="eyebrow">FAQ</p>
          <h2>Common questions.</h2>
        </div>
        <div className="faq-grid">
          <details open>
            <summary>How do I book a court?</summary>
            <p>Head to the Book page, pick your sport and date, select an available slot, and fill in your details. You'll get a booking reference immediately.</p>
          </details>
          <details>
            <summary>Which sports are available?</summary>
            <p>Cricket, Badminton, and Pickleball are available. More sports may be added in future.</p>
          </details>
          <details>
            <summary>Can my company plan an event?</summary>
            <p>Yes. Use the corporate enquiry form on the Contact page and our team will get back to you to plan your event.</p>
          </details>
          <details>
            <summary>What is the maximum group size?</summary>
            <p>Cricket supports up to 11 players, Pickleball up to 6, and Badminton up to 4 per court slot. For larger groups, use the corporate enquiry form.</p>
          </details>
        </div>
      </section>
    </>
  );
}
