import { useEffect, useState } from "react";
import { getVenueInfo } from "./api";

/** Venue contact details as entered in Admin → Contact Details (empty strings until loaded or when not set). */
export type VenueInfo = {
  address: string;
  phone: string;
  email: string;
  hours: string;
  instagram: string;
  facebook: string;
};

const EMPTY: VenueInfo = { address: "", phone: "", email: "", hours: "", instagram: "", facebook: "" };

export function useVenueInfo(): VenueInfo {
  const [info, setInfo] = useState<VenueInfo>(EMPTY);
  useEffect(() => {
    let alive = true;
    getVenueInfo()
      .then((v) => {
        if (!alive) return;
        setInfo({
          address: v.venue_address ?? "",
          phone: v.venue_phone ?? "",
          email: v.venue_email ?? "",
          hours: v.venue_hours ?? "",
          instagram: v.social_instagram ?? "",
          facebook: v.social_facebook ?? "",
        });
      })
      .catch(() => {}); // the footer simply shows nothing extra when the details cannot be loaded
    return () => { alive = false; };
  }, []);
  return info;
}
