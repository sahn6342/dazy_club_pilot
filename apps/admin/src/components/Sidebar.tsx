import { NavLink } from "react-router-dom";

const NAV = [
  { to: "/", label: "Dashboard", icon: "⬛" },
  { to: "/bookings", label: "Bookings", icon: "📅" },
  { to: "/schedule", label: "Schedule", icon: "🗓" },
  { to: "/promos", label: "Promos", icon: "🏷" },
  { to: "/enquiries", label: "Enquiries", icon: "✉️" },
  { to: "/gallery", label: "Gallery", icon: "🖼" },
  { to: "/testimonials", label: "Testimonials", icon: "💬" },
  { to: "/cms", label: "CMS", icon: "✏️" },
  { to: "/users", label: "Managers", icon: "👤" },
];

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="brand-text">Dazy Admin</span>
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
      </nav>
    </aside>
  );
}
