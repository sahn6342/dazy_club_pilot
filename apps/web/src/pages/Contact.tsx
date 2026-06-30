import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { launchSports } from "@dazy/shared";
import { submitContactEnquiry, submitCorporateEnquiry, todayIso } from "../lib/api";
import { validateName, validateContact, validateCompany, validateGroupSize } from "../lib/validate";

const API = (import.meta as any).env?.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
type VenueInfo = { address: string; phone: string; email: string; hours: string; instagram: string; facebook: string };

function useVenueInfo(): VenueInfo {
  const [info, setInfo] = useState<VenueInfo>({ address: "", phone: "", email: "", hours: "", instagram: "", facebook: "" });
  useEffect(() => {
    fetch(`${API}/venue`)
      .then((r) => r.json())
      .then((entries: { key: string; value: string }[]) => {
        const v = Object.fromEntries(entries.map((e) => [e.key, e.value]));
        setInfo({
          address:   v.venue_address   ?? "",
          phone:     v.venue_phone     ?? "",
          email:     v.venue_email     ?? "",
          hours:     v.venue_hours     ?? "",
          instagram: v.social_instagram ?? "",
          facebook:  v.social_facebook  ?? "",
        });
      })
      .catch(() => {});
  }, []);
  return info;
}

type FormStatus = "idle" | "submitting" | "success" | "error";

export function Contact() {
  const [searchParams] = useSearchParams();
  const initialTab = searchParams.get("tab") === "corporate" ? "corporate" : "contact";
  const [tab, setTab] = useState<"contact" | "corporate">(initialTab);
  const venue = useVenueInfo();

  const hasVenueInfo = venue.address || venue.phone || venue.email || venue.hours;

  return (
    <section id="contact" className="section">
      <div className="section-heading">
        <p className="eyebrow">Get in touch</p>
        <h2>Questions or planning an event?</h2>
        <p>Send a general enquiry, or tell us about a corporate event.</p>
      </div>

      {hasVenueInfo && (
        <div className="venue-info-band">
          {venue.address && (
            <div className="venue-info-item">
              <span className="venue-info-icon">📍</span>
              <span>{venue.address}</span>
            </div>
          )}
          {venue.phone && (
            <div className="venue-info-item">
              <span className="venue-info-icon">📞</span>
              <a href={`tel:${venue.phone.replace(/\s/g, "")}`}>{venue.phone}</a>
            </div>
          )}
          {venue.email && (
            <div className="venue-info-item">
              <span className="venue-info-icon">✉️</span>
              <a href={`mailto:${venue.email}`}>{venue.email}</a>
            </div>
          )}
          {venue.hours && (
            <div className="venue-info-item">
              <span className="venue-info-icon">🕐</span>
              <span>{venue.hours}</span>
            </div>
          )}
          {(venue.instagram || venue.facebook) && (
            <div className="venue-info-item">
              <span className="venue-info-icon">🔗</span>
              <span>
                {venue.instagram && <a href={venue.instagram} target="_blank" rel="noopener noreferrer">Instagram</a>}
                {venue.instagram && venue.facebook && " · "}
                {venue.facebook && <a href={venue.facebook} target="_blank" rel="noopener noreferrer">Facebook</a>}
              </span>
            </div>
          )}
        </div>
      )}

      <div className="sport-tabs" role="tablist">
        <button role="tab" className={`tab-btn${tab === "contact" ? " active" : ""}`} onClick={() => setTab("contact")}>
          General enquiry
        </button>
        <button role="tab" className={`tab-btn${tab === "corporate" ? " active" : ""}`} onClick={() => setTab("corporate")}>
          Corporate event
        </button>
      </div>

      {tab === "contact" ? <ContactForm /> : <CorporateForm />}
    </section>
  );
}

// ── Shared helpers ────────────────────────────────────────────────────────────

function FieldError({ msg }: { msg?: string }) {
  if (!msg) return null;
  return <p className="field-error">{msg}</p>;
}

function useField(initial = "") {
  const [value, setValue] = useState(initial);
  const [touched, setTouch] = useState(false);
  return {
    value,
    touched,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setValue(e.target.value),
    onBlur: () => setTouch(true),
    reset: () => { setValue(initial); setTouch(false); },
  };
}

// ── Contact form ──────────────────────────────────────────────────────────────

function ContactForm() {
  const [status, setStatus] = useState<FormStatus>("idle");
  const name = useField();
  const contact = useField();

  const nameErr = name.touched ? (validateName(name.value) ?? undefined) : undefined;
  const contactErr = contact.touched ? (validateContact(contact.value) ?? undefined) : undefined;

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formEl = event.currentTarget;

    // Force-touch all validated fields
    name.onBlur(); contact.onBlur();
    if (validateName(name.value) || validateContact(contact.value)) return;

    setStatus("submitting");
    const data = Object.fromEntries(new FormData(formEl));
    try {
      await submitContactEnquiry({
        name: name.value.trim(),
        contact: contact.value.trim(),
        interestedSport: String(data.interestedSport || ""),
        message: String(data.message || ""),
      });
      setStatus("success");
      name.reset(); contact.reset();
      formEl.reset();
    } catch {
      setStatus("error");
    }
  }

  return (
    <form className="form-card" onSubmit={onSubmit} noValidate>
      <div className="field-group">
        <label>
          Name
          <input value={name.value} onChange={name.onChange} onBlur={name.onBlur} className={nameErr ? "input-error" : ""} placeholder="Your name" />
        </label>
        <FieldError msg={nameErr} />
      </div>

      <div className="field-group">
        <label>
          Phone or email
          <input value={contact.value} onChange={contact.onChange} onBlur={contact.onBlur} className={contactErr ? "input-error" : ""} placeholder="10-digit mobile or email" />
        </label>
        <FieldError msg={contactErr} />
      </div>

      <label>
        Interested sport
        <select name="interestedSport" defaultValue="">
          <option value="">Any / not sure</option>
          {launchSports.map((s) => (
            <option key={s.slug} value={s.slug}>{s.name}</option>
          ))}
        </select>
      </label>

      <label>Message <textarea name="message" rows={5} /></label>

      <button className="button primary" type="submit" disabled={status === "submitting"}>
        {status === "submitting" ? "Sending…" : "Send message"}
      </button>
      <StatusMessage status={status} />
    </form>
  );
}

// ── Corporate form ────────────────────────────────────────────────────────────

function CorporateForm() {
  const [status, setStatus] = useState<FormStatus>("idle");
  const contactName = useField();
  const company = useField();
  const contact = useField();
  const [groupSize, setGroupSize] = useState("1");
  const [groupTouched, setGroupTouched] = useState(false);

  const contactNameErr = contactName.touched ? (validateName(contactName.value) ?? undefined) : undefined;
  const companyErr = company.touched ? (validateCompany(company.value) ?? undefined) : undefined;
  const contactErr = contact.touched ? (validateContact(contact.value) ?? undefined) : undefined;
  const groupSizeErr = groupTouched ? (validateGroupSize(Number(groupSize)) ?? undefined) : undefined;

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formEl = event.currentTarget;

    // Touch all fields
    contactName.onBlur(); company.onBlur(); contact.onBlur(); setGroupTouched(true);

    if (
      validateName(contactName.value) ||
      validateCompany(company.value) ||
      validateContact(contact.value) ||
      validateGroupSize(Number(groupSize))
    ) return;

    setStatus("submitting");
    const data = Object.fromEntries(new FormData(formEl));
    try {
      await submitCorporateEnquiry({
        contactName: contactName.value.trim(),
        company: company.value.trim(),
        contact: contact.value.trim(),
        estimatedGroupSize: Number(groupSize),
        eventType: String(data.eventType || ""),
        preferredDate: String(data.preferredDate || ""),
        preferredSport: String(data.preferredSport || ""),
        message: String(data.message || ""),
      });
      setStatus("success");
      contactName.reset(); company.reset(); contact.reset();
      setGroupSize("1"); setGroupTouched(false);
      formEl.reset();
    } catch {
      setStatus("error");
    }
  }

  return (
    <form className="form-card" onSubmit={onSubmit} noValidate>
      <div className="field-group">
        <label>
          Contact name
          <input value={contactName.value} onChange={contactName.onChange} onBlur={contactName.onBlur} className={contactNameErr ? "input-error" : ""} placeholder="Your name" />
        </label>
        <FieldError msg={contactNameErr} />
      </div>

      <div className="field-group">
        <label>
          Company
          <input value={company.value} onChange={company.onChange} onBlur={company.onBlur} className={companyErr ? "input-error" : ""} placeholder="Company name" />
        </label>
        <FieldError msg={companyErr} />
      </div>

      <div className="field-group">
        <label>
          Phone or email
          <input value={contact.value} onChange={contact.onChange} onBlur={contact.onBlur} className={contactErr ? "input-error" : ""} placeholder="10-digit mobile or email" />
        </label>
        <FieldError msg={contactErr} />
      </div>

      <label>Event type <input name="eventType" placeholder="e.g. team outing, tournament" /></label>

      <div className="field-group">
        <label>
          Estimated group size
          <input
            type="number"
            min="1"
            value={groupSize}
            onChange={(e) => setGroupSize(e.target.value)}
            onBlur={() => setGroupTouched(true)}
            className={groupSizeErr ? "input-error" : ""}
          />
        </label>
        <FieldError msg={groupSizeErr} />
      </div>

      <label>Preferred date <input name="preferredDate" type="date" min={todayIso()} /></label>

      <label>
        Preferred sport
        <select name="preferredSport" defaultValue="">
          <option value="">No preference</option>
          {launchSports.map((s) => (
            <option key={s.slug} value={s.slug}>{s.name}</option>
          ))}
        </select>
      </label>

      <label>Message <textarea name="message" rows={4} /></label>

      <button className="button primary" type="submit" disabled={status === "submitting"}>
        {status === "submitting" ? "Submitting…" : "Submit enquiry"}
      </button>
      <StatusMessage status={status} />
    </form>
  );
}

function StatusMessage({ status }: { status: FormStatus }) {
  if (status === "success") return <p className="form-message success">Thanks! We'll be in touch soon.</p>;
  if (status === "error") return <p className="form-message error">Something went wrong. Please try again.</p>;
  return null;
}
