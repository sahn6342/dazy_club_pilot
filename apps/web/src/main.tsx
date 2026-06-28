import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import {
  futureCapabilities,
  galleryItems,
  launchSports,
  notifications,
  testimonials,
  type ContactEnquiry,
  type CorporateEnquiry
} from "@dazy/shared";
import { launchBadge } from "@dazy/ui";
import "./styles.css";

type FormStatus = "idle" | "success" | "error";

function App() {
  const [contactStatus, setContactStatus] = useState<FormStatus>("idle");
  const [corporateStatus, setCorporateStatus] = useState<FormStatus>("idle");

  function submitContact(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget));
    const enquiry: ContactEnquiry = {
      name: String(data.name || ""),
      contact: String(data.contact || ""),
      interestedSport: String(data.sport || ""),
      message: String(data.message || "")
    };
    setContactStatus(enquiry.name && enquiry.contact ? "success" : "error");
  }

  function submitCorporate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget));
    const enquiry: CorporateEnquiry = {
      contactName: String(data.contactName || ""),
      company: String(data.company || ""),
      contact: String(data.contact || ""),
      eventType: String(data.eventType || ""),
      estimatedGroupSize: Number(data.estimatedGroupSize || 0),
      preferredDate: String(data.preferredDate || ""),
      preferredSport: String(data.preferredSport || ""),
      message: String(data.message || "")
    };
    setCorporateStatus(enquiry.contactName && enquiry.company && enquiry.contact ? "success" : "error");
  }

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#home">Dazy.club</a>
        <nav aria-label="Primary navigation">
          <a href="#sports">Sports</a>
          <a href="#gallery">Gallery</a>
          <a href="#corporate">Corporate</a>
          <a href="#contact">Contact</a>
        </nav>
      </header>

      <section id="home" className="hero section">
        <p className="eyebrow">{launchBadge}</p>
        <h1>Premium sports energy, built for your next game.</h1>
        <p className="hero-copy">
          Browse Cricket, Badminton, and Pickleball at Dazy.club. First launch supports discovery,
          gallery proof, testimonials, and enquiries while live booking is prepared for the next phase.
        </p>
        <div className="actions">
          <a className="button primary" href="#contact">Enquire now</a>
          <a className="button secondary" href="#sports">View sports</a>
        </div>
        <div className="notice" role="status">
          <strong>{notifications[0].title}:</strong> {notifications[0].body}
        </div>
      </section>

      <section id="sports" className="section">
        <div className="section-heading">
          <p className="eyebrow">Sports</p>
          <h2>Choose your court energy.</h2>
          <p>Launch content is seeded and replaceable. Booking CTAs route to enquiry for now.</p>
        </div>
        <div className="card-grid">
          {launchSports.map((sport) => (
            <article className="card sport-card" key={sport.id}>
              <div className="media-gradient" aria-hidden="true" />
              <p className="eyebrow">{sport.name}</p>
              <h3>{sport.tagline}</h3>
              <p>{sport.description}</p>
              <ul>
                {sport.highlights.map((highlight) => (
                  <li key={highlight}>{highlight}</li>
                ))}
              </ul>
              <a className="text-link" href="#contact">Ask about {sport.name}</a>
            </article>
          ))}
        </div>
      </section>

      <section id="gallery" className="section split">
        <div>
          <p className="eyebrow">Dazy memories</p>
          <h2>Seeded gallery proof for the first design/build.</h2>
          <p>These cards stand in for real photography and can be replaced once final assets arrive.</p>
        </div>
        <div className="mini-grid">
          {galleryItems.map((item) => (
            <article className="card compact" key={item.id}>
              <div className="media-gradient small" aria-hidden="true" />
              <h3>{item.title}</h3>
              <p>{item.sportSlug} / {item.tone}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">Testimonials</p>
          <h2>Trust signals before live booking.</h2>
        </div>
        <div className="card-grid two">
          {testimonials.map((item) => (
            <article className="card" key={item.id}>
              <p className="quote">"{item.quote}"</p>
              <p className="byline">{item.name} - {item.context}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="corporate" className="section split">
        <div>
          <p className="eyebrow">Corporate events</p>
          <h2>Plan team outings, tournaments, and private sports days.</h2>
          <p>Group enquiries are launch scope. CRM automation and admin workflows come later.</p>
        </div>
        <form className="form-card" onSubmit={submitCorporate}>
          <label>Contact name<input name="contactName" /></label>
          <label>Company<input name="company" /></label>
          <label>Phone or email<input name="contact" /></label>
          <label>Event type<input name="eventType" /></label>
          <label>Estimated group size<input name="estimatedGroupSize" type="number" min="1" /></label>
          <label>Preferred date<input name="preferredDate" type="date" /></label>
          <label>Preferred sport<input name="preferredSport" /></label>
          <label>Message<textarea name="message" rows={4} /></label>
          <button className="button primary" type="submit">Submit corporate enquiry</button>
          <FormMessage status={corporateStatus} />
        </form>
      </section>

      <section id="contact" className="section split">
        <div>
          <p className="eyebrow">Contact</p>
          <h2>Ready to play? Send an enquiry.</h2>
          <p>Live booking, OTP, and payment are intentionally deferred. This form is the launch conversion path.</p>
          <div className="future-box">
            <h3>Future-ready structure</h3>
            <ul>
              {futureCapabilities.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </div>
        </div>
        <form className="form-card" onSubmit={submitContact}>
          <label>Name<input name="name" /></label>
          <label>Phone or email<input name="contact" /></label>
          <label>Interested sport<input name="sport" /></label>
          <label>Message<textarea name="message" rows={5} /></label>
          <button className="button primary" type="submit">Submit enquiry</button>
          <FormMessage status={contactStatus} />
        </form>
      </section>

      <section className="section faq">
        <p className="eyebrow">FAQ</p>
        <h2>Launch-safe answers.</h2>
        <details>
          <summary>Can I book online now?</summary>
          <p>Not yet. First launch captures enquiries. Live booking, OTP, and payment are future scope.</p>
        </details>
        <details>
          <summary>Which sports are included?</summary>
          <p>Cricket, Badminton, and Pickleball are included in the first launch content.</p>
        </details>
        <details>
          <summary>Can my company plan an event?</summary>
          <p>Yes. Use the corporate enquiry form and the team can follow up manually.</p>
        </details>
      </section>

      <footer className="footer">
        <strong>Dazy.club</strong>
        <span>Premium sports experience. Browse + enquiry launch.</span>
      </footer>
    </main>
  );
}

function FormMessage({ status }: { status: FormStatus }) {
  if (status === "idle") return null;
  if (status === "success") return <p className="form-message success">Thanks. Your enquiry is ready for API persistence.</p>;
  return <p className="form-message error">Please add the required contact details before submitting.</p>;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
