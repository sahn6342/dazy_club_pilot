import { NavLink, Link, Outlet } from "react-router-dom";
import { BRAND } from "@dazy/shared";
import { WhatsappFab } from "./WhatsappFab";
import { useVenueInfo } from "../lib/useVenueInfo";

export function Layout() {
  const venue = useVenueInfo();
  const hasContact = venue.address || venue.phone || venue.email || venue.hours || venue.instagram || venue.facebook;
  return (
    <main>
      <header className="site-header">
        <Link className="brand" to="/">
          <img className="brand-logo" src="/images/logo-sm.webp" alt={BRAND.name} width="70" height="60" />
        </Link>
        <nav aria-label="Primary navigation">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>Home</NavLink>
          <NavLink to="/book" className={({ isActive }) => (isActive ? "active" : "")}>Book</NavLink>
          <NavLink to="/my-bookings" className={({ isActive }) => (isActive ? "active" : "")}>My Bookings</NavLink>
          <NavLink to="/contact" className={({ isActive }) => (isActive ? "active" : "")}>Contact</NavLink>
        </nav>
      </header>

      <Outlet />

      <footer className="footer">
        <div className="footer-about">
          <strong className="footer-brand">
            <img className="brand-logo" src="/images/logo-sm.webp" alt={BRAND.name} width="47" height="40" loading="lazy" />
          </strong>
          <span>Premium sports experience. Cricket, Football, Badminton &amp; Pickleball.</span>
        </div>

        {hasContact && (
          <ul className="footer-contact" data-testid="footer-contact" aria-label="Contact details">
            {venue.address && (
              <li data-testid="footer-address">
                <span className="footer-icon" aria-hidden="true">📍</span>
                <a href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.address)}`} target="_blank" rel="noopener noreferrer">
                  {venue.address}
                </a>
              </li>
            )}
            {venue.phone && (
              <li data-testid="footer-phone">
                <span className="footer-icon" aria-hidden="true">📞</span>
                <a href={`tel:${venue.phone.replace(/[^\d+]/g, "")}`}>{venue.phone}</a>
              </li>
            )}
            {venue.email && (
              <li data-testid="footer-email">
                <span className="footer-icon" aria-hidden="true">✉️</span>
                <a href={`mailto:${venue.email}`}>{venue.email}</a>
              </li>
            )}
            {venue.hours && (
              <li data-testid="footer-hours">
                <span className="footer-icon" aria-hidden="true">🕐</span>
                <span>{venue.hours}</span>
              </li>
            )}
            {(venue.instagram || venue.facebook) && (
              <li data-testid="footer-social">
                <span className="footer-icon" aria-hidden="true">🔗</span>
                <span>
                  {venue.instagram && <a href={venue.instagram} target="_blank" rel="noopener noreferrer">Instagram</a>}
                  {venue.instagram && venue.facebook && " · "}
                  {venue.facebook && <a href={venue.facebook} target="_blank" rel="noopener noreferrer">Facebook</a>}
                </span>
              </li>
            )}
          </ul>
        )}
      </footer>
      <WhatsappFab />
    </main>
  );
}
