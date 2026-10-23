import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { clearToken } from "../lib/auth";

export type KioskPage = "menu" | "orders" | "tables" | "kds";

const PAGES: { page: KioskPage; label: string; to: string }[] = [
  { page: "menu", label: "Menu", to: "/menu" },
  { page: "orders", label: "Orders", to: "/orders" },
  { page: "tables", label: "Tables", to: "/tables" },
  { page: "kds", label: "KDS", to: "/kds" },
];

/** Same breakpoint as the mobile rules in styles.css: at or below 720px the buttons sit behind a menu button. */
const DESKTOP_NAV = "(min-width: 721px)";

/** The top bar shared by every signed-in kiosk page. `active` marks the page being shown. */
export function KioskHeader({ active }: { active: KioskPage }) {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const headerRef = useRef<HTMLElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);

  function logout() {
    clearToken();
    navigate("/login");
  }

  function go(to: string) {
    setMenuOpen(false);
    navigate(to);
  }

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

  return (
    <header className="kiosk-header" ref={headerRef}>
      <span className="kiosk-logo"><img className="kiosk-logo-img" src="/logo-sm.webp" alt="" width="40" height="34" />Kiosk</span>
      <button
        type="button"
        ref={toggleRef}
        className="nav-toggle"
        data-testid="nav-toggle"
        aria-label={menuOpen ? "Close menu" : "Open menu"}
        aria-expanded={menuOpen}
        aria-controls="kiosk-menu"
        onClick={() => setMenuOpen((open) => !open)}
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          {menuOpen ? <path d="M5 5l14 14M19 5L5 19" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
        </svg>
      </button>
      <div id="kiosk-menu" className={`kiosk-menu${menuOpen ? " open" : ""}`}>
        <nav className="kiosk-nav" aria-label="Kiosk navigation">
          {PAGES.map(({ page, label, to }) => (
            <button
              key={page}
              className={`kiosk-nav-btn${page === active ? " active" : ""}`}
              aria-current={page === active ? "page" : undefined}
              onClick={() => go(to)}
            >
              {label}
            </button>
          ))}
        </nav>
        <button className="kiosk-logout" onClick={logout}>Logout</button>
      </div>
    </header>
  );
}
