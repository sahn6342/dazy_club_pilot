import { useVenueInfo } from "../lib/useVenueInfo";

/** Slim one-line version of the website footer: the venue's address, phone and hours from the CMS. */
export function KioskFooter() {
  const venue = useVenueInfo();
  if (!venue.address && !venue.phone && !venue.hours) return null;
  return (
    <footer className="kiosk-footer" data-testid="kiosk-footer">
      <img className="kiosk-footer-logo" src="/logo-sm.webp" alt="" width="24" height="20" />
      {venue.address && (
        <a data-testid="footer-address" href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.address)}`} target="_blank" rel="noopener noreferrer">
          <span aria-hidden="true">📍</span> {venue.address}
        </a>
      )}
      {venue.phone && (
        <a data-testid="footer-phone" href={`tel:${venue.phone.replace(/[^\d+]/g, "")}`}>
          <span aria-hidden="true">📞</span> {venue.phone}
        </a>
      )}
      {venue.hours && (
        <span data-testid="footer-hours"><span aria-hidden="true">🕐</span> {venue.hours}</span>
      )}
    </footer>
  );
}
