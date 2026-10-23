import { useEffect, useRef, useState } from "react";
import { NavLink, Link, Outlet, useLocation } from "react-router-dom";
import { BRAND } from "@dazy/shared";
import { WhatsappFab } from "./WhatsappFab";
import { useVenueInfo } from "../lib/useVenueInfo";

/** Same breakpoint as the mobile styles in styles.css: at or below it the links sit behind a menu button. */
const DESKTOP_NAV = "(min-width: 721px)";

export function Layout() {
  const venue = useVenueInfo();
  const hasContact = venue.address || venue.phone || venue.email || venue.hours || venue.instagram || venue.facebook;

  const [menuOpen, setMenuOpen] = useState(false);
  const { pathname } = useLocation();
  const headerRef = useRef<HTMLElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const closeMenu = () => setMenuOpen(false);

  useEffect(() => { setMenuOpen(false); }, [pathname]);

  // While the menu is open: Escape, a tap outside the header, or growing to desktop width closes it.
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setMenuOpen(false); toggleRef.current?.focus(); }
    };
    const onPointer = (e: PointerEvent) => {
      if (!headerRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    const desktop = window.matchMedia(DESKTOP_NAV);
    const onResize = () => { if (desktop.matches) setMenuOpen(false); };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    desktop.addEventListener("change", onResize);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
      desktop.removeEventListener("change", onResize);
    };
  }, [menuOpen]);

  const link = ({ isActive }: { isActive: boolean }) => (isActive ? "active" : "");
  return (
    <main>
      <header className="site-header" ref={headerRef}>
        <Link className="brand" to="/">
          <img className="brand-logo" src="/images/logo-sm.webp" alt={BRAND.name} width="70" height="60" />
        </Link>
        <button
          type="button"
          ref={toggleRef}
          className="nav-toggle"
          data-testid="nav-toggle"
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          aria-controls="primary-nav"
          onClick={() => setMenuOpen((open) => !open)}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            {menuOpen ? <path d="M5 5l14 14M19 5L5 19" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
          </svg>
        </button>
        <nav id="primary-nav" className={menuOpen ? "open" : ""} aria-label="Primary navigation">
          <NavLink to="/" end className={link} onClick={closeMenu}>Home</NavLink>
          <NavLink to="/book" className={link} onClick={closeMenu}>Book</NavLink>
          <NavLink to="/my-bookings" className={link} onClick={closeMenu}>My Bookings</NavLink>
          <NavLink to="/contact" className={link} onClick={closeMenu}>Contact</NavLink>
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
