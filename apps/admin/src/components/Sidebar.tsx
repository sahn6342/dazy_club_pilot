import { NavLink } from "react-router-dom";
import { BRAND } from "@dazy/shared";

const NAV = [
  { to: "/", label: "Dashboard", icon: "⬛" },
  { to: "/bookings", label: "Bookings", icon: "📅" },
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

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <img className="brand-logo" src="/logo-sm.webp" alt="" width="46" height="40" />
        <span className="brand-text">{BRAND.adminTitle}</span>
      </div>
      <nav className="sidebar-nav">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
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
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
