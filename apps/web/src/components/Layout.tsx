import { NavLink, Link, Outlet } from "react-router-dom";

export function Layout() {
  return (
    <main>
      <header className="site-header">
        <Link className="brand" to="/">Dazy.club</Link>
        <nav aria-label="Primary navigation">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>Home</NavLink>
          <NavLink to="/book" className={({ isActive }) => (isActive ? "active" : "")}>Book</NavLink>
          <NavLink to="/contact" className={({ isActive }) => (isActive ? "active" : "")}>Contact</NavLink>
        </nav>
      </header>

      <Outlet />

      <footer className="footer">
        <strong>Dazy.club</strong>
        <span>Premium sports experience. Cricket, Badminton &amp; Pickleball.</span>
      </footer>
    </main>
  );
}
