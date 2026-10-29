import { useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import { BRAND } from "@dazy/shared";

const NAV = [
  { to: "/", label: "Dashboard", icon: "⬛" },
  { to: "/bookings", label: "Bookings", icon: "📅" },
  { to: "/bills", label: "Bills", icon: "🧮" },
  { to: "/schedule", label: "Schedule", icon: "🗓" },
  { to: "/promos", label: "Promos", icon: "🏷" },
  { to: "/enquiries", label: "Enquiries", icon: "✉️" },
  { to: "/gallery", label: "Gallery", icon: "🖼" },
  { to: "/testimonials", label: "Testimonials", icon: "💬" },
  { to: "/cms", label: "CMS", icon: "✏️" },
  { to: "/courts", label: "Courts", icon: "🏟" },
  { to: "/contact-details", label: "Contact Details", icon: "📍" },
  { to: "/users", label: "Manage Users", icon: "👥" },
  { to: "/audit", label: "Audit log", icon: "🧾" },
  { to: "/notifications", label: "Notifications", icon: "🔔" },
];

const CAFE_NAV = [
  { to: "/cafe/categories", label: "Categories", icon: "🍽" },
  { to: "/cafe/items", label: "Menu Items", icon: "🥗" },
  { to: "/cafe/tables", label: "Tables", icon: "🪑" },
  { to: "/cafe/settings", label: "Café Settings", icon: "☕" },
  { to: "/cafe/orders", label: "Orders", icon: "🧾" },
];

/** Same breakpoint as the mobile rules in styles.css: at or below 760px the links sit behind a menu button. */
const DESKTOP_NAV = "(min-width: 761px)";

export function Sidebar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const asideRef = useRef<HTMLElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const closeMenu = () => setMenuOpen(false);

  // While the menu is open: Escape, a tap outside the sidebar, or growing to desktop width closes it.
  // (Every page renders its own Sidebar, so choosing a link also starts a fresh, closed one.)
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setMenuOpen(false); toggleRef.current?.focus(); }
    };
    const onPointer = (e: PointerEvent) => {
      if (!asideRef.current?.contains(e.target as Node)) setMenuOpen(false);
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

  return (
    <aside className="sidebar" ref={asideRef}>
      <div className="sidebar-brand">
        <img className="brand-logo" src="/logo-sm.webp" alt="" width="46" height="40" />
        <span className="brand-text">{BRAND.adminTitle}</span>
      </div>
      <button
        type="button"
        ref={toggleRef}
        className="nav-toggle"
        data-testid="nav-toggle"
        aria-label={menuOpen ? "Close menu" : "Open menu"}
        aria-expanded={menuOpen}
        aria-controls="admin-nav"
        onClick={() => setMenuOpen((open) => !open)}
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          {menuOpen ? <path d="M5 5l14 14M19 5L5 19" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
        </svg>
      </button>
      <nav id="admin-nav" className={`sidebar-nav${menuOpen ? " open" : ""}`} aria-label="Admin navigation">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
            onClick={closeMenu}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
        <div className="sidebar-section-label">Café POS</div>
        {CAFE_NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
            onClick={closeMenu}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
