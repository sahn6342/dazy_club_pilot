import { useEffect, useState } from "react";
import { api } from "./api";

/** Venue contact details as entered in Admin -> Contact Details (empty strings until loaded or when not set). */
export type VenueInfo = { address: string; phone: string; hours: string };

const EMPTY: VenueInfo = { address: "", phone: "", hours: "" };

let venuePromise: Promise<Record<string, string>> | null = null;

/** The public GET /venue list as a key -> value map; one request per page load, retried after a failure. */
function getVenue(): Promise<Record<string, string>> {
  if (!venuePromise) {
    venuePromise = api.get<{ key: string; value: string }[]>("/venue")
      .then((entries) => Object.fromEntries(entries.map((e) => [e.key, e.value])))
      .catch((e) => { venuePromise = null; throw e; });
  }
  return venuePromise;
}

export function useVenueInfo(): VenueInfo {
  const [info, setInfo] = useState<VenueInfo>(EMPTY);
  useEffect(() => {
    let alive = true;
    getVenue()
      .then((v) => {
        if (alive) setInfo({ address: v.venue_address ?? "", phone: v.venue_phone ?? "", hours: v.venue_hours ?? "" });
      })
      .catch(() => {}); // no strip when the details cannot be loaded: the POS keeps its full height
    return () => { alive = false; };
  }, []);
  return info;
}
