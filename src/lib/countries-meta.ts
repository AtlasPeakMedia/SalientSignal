/**
 * ISO 3166-1 alpha-2 → display metadata lookup.
 *
 * Built from the existing dummy fixture (151 countries, US/FVEY excluded).
 * The real data layer uses this to hydrate Supabase rows (which only store
 * the 2-char country code) with names, flags, and regions for rendering.
 */

import { COUNTRY_ACTIVITY } from "./dummy-data";

export interface CountryMeta {
  iso2: string;
  name: string;
  flag: string;
  region: string;
}

/** Pre-built lookup map: ISO2 → metadata. */
const META_BY_ISO: Map<string, CountryMeta> = new Map(
  COUNTRY_ACTIVITY.map((c) => [
    c.iso2,
    { iso2: c.iso2, name: c.name, flag: c.flag, region: c.region },
  ]),
);

export function getCountryMeta(iso2: string): CountryMeta | null {
  return META_BY_ISO.get(iso2.toUpperCase()) ?? null;
}

/** All monitored country ISO2 codes (151 at launch). */
export function listMonitoredIsoCodes(): string[] {
  return Array.from(META_BY_ISO.keys());
}
