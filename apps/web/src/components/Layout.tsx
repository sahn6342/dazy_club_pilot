import { NavLink, Link, Outlet } from "react-router-dom";
import { BRAND } from "@dazy/shared";
import { WhatsappFab } from "./WhatsappFab";

export function Layout() {
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
        <strong className="footer-brand">
          <img className="brand-logo" src="/images/logo-sm.webp" alt={BRAND.name} width="47" height="40" loading="lazy" />
        </strong>
        <span>Premium sports experience. Cricket, Football, Badminton &amp; Pickleball.</span>
      </footer>
      <WhatsappFab />
    </main>
  );
}
