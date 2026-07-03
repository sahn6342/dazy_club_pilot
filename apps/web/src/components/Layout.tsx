import { NavLink, Link, Outlet } from "react-router-dom";
import { BRAND } from "@dazy/shared";

export function Layout() {
  return (
    <main>
      <header className="site-header">
        <Link className="brand" to="/">{BRAND.name}</Link>
        <nav aria-label="Primary navigation">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>Home</NavLink>
          <NavLink to="/book" className={({ isActive }) => (isActive ? "active" : "")}>Book</NavLink>
          <NavLink to="/my-bookings" className={({ isActive }) => (isActive ? "active" : "")}>My Bookings</NavLink>
          <NavLink to="/contact" className={({ isActive }) => (isActive ? "active" : "")}>Contact</NavLink>
        </nav>
      </header>

      <Outlet />

      <footer className="footer">
        <strong>{BRAND.name}</strong>
        <span>Premium sports experience. Cricket, Badminton &amp; Pickleball.</span>
      </footer>
    </main>
  );
}
