/**
 * Country → region mapping for the globe's RegionFilter.
 *
 * Organized into the 18 regions that make sense for a state-media
 * intelligence product. These are NOT strict UN M49 regions — we group
 * by operational relevance (e.g. "Central Asia" = the 5 'stans + Mongolia,
 * "Middle East" includes Turkey because of its state media posture, "Russia
 * & Caucasus" keeps the post-Soviet orbit together).
 *
 * FVEY countries (US, GB, CA, AU, NZ) are intentionally absent — the product
 * doesn't monitor them and they wouldn't belong in any region filter.
 *
 * Used by src/components/Globe/RegionFilter.tsx and HomePageClient.tsx to
 * filter the globe view to selected regions.
 */

export type Region =
  | "EAST_ASIA"
  | "SOUTHEAST_ASIA"
  | "SOUTH_ASIA"
  | "CENTRAL_ASIA"
  | "MIDDLE_EAST"
  | "NORTH_AFRICA"
  | "WEST_AFRICA"
  | "CENTRAL_AFRICA"
  | "EAST_AFRICA"
  | "SOUTHERN_AFRICA"
  | "RUSSIA_CAUCASUS"
  | "EASTERN_EUROPE"
  | "WESTERN_EUROPE"
  | "OCEANIA"
  | "CARIBBEAN"
  | "CENTRAL_AMERICA"
  | "SOUTH_AMERICA";

/** Display order for the region filter dropdown. */
export const REGIONS: { value: Region; label: string }[] = [
  { value: "EAST_ASIA", label: "East Asia" },
  { value: "SOUTHEAST_ASIA", label: "Southeast Asia" },
  { value: "SOUTH_ASIA", label: "South Asia" },
  { value: "CENTRAL_ASIA", label: "Central Asia" },
  { value: "MIDDLE_EAST", label: "Middle East" },
  { value: "NORTH_AFRICA", label: "North Africa" },
  { value: "WEST_AFRICA", label: "West Africa" },
  { value: "CENTRAL_AFRICA", label: "Central Africa" },
  { value: "EAST_AFRICA", label: "East Africa" },
  { value: "SOUTHERN_AFRICA", label: "Southern Africa" },
  { value: "RUSSIA_CAUCASUS", label: "Russia & Caucasus" },
  { value: "EASTERN_EUROPE", label: "Eastern Europe" },
  { value: "WESTERN_EUROPE", label: "Western Europe" },
  { value: "OCEANIA", label: "Oceania" },
  { value: "CARIBBEAN", label: "Caribbean" },
  { value: "CENTRAL_AMERICA", label: "Central America" },
  { value: "SOUTH_AMERICA", label: "South America" },
];

/**
 * ISO 3166-1 alpha-2 → region mapping.
 *
 * Covers every country currently in outlets.json (81 as of B8) plus a
 * superset of 150+ others so future outlet additions don't need a mapping
 * update. Any ISO code not in this map falls through to `getRegion() → null`
 * and the country shows as "unassigned" in the filter.
 *
 * Notes on assignments:
 *   - Turkey (TR) → Middle East (operational relevance, not geography)
 *   - Russia (RU) → Russia & Caucasus (its own bucket given the state media
 *     volume — merging with Eastern Europe would let it dominate that filter)
 *   - Ukraine (UA), Belarus (BY), Moldova (MD) → Eastern Europe (post-Soviet
 *     but not Russian orbit in the current media posture)
 *   - Iran (IR) → Middle East
 *   - Egypt (EG), Libya (LY), Tunisia (TN), Algeria (DZ), Morocco (MA),
 *     Sudan (SD), Mauritania (MR) → North Africa
 *   - Ethiopia (ET), Eritrea (ER) → East Africa
 *   - Mongolia (MN) → East Asia
 */
export const COUNTRY_TO_REGION: Record<string, Region> = {
  // East Asia
  CN: "EAST_ASIA",
  JP: "EAST_ASIA",
  KR: "EAST_ASIA",
  KP: "EAST_ASIA",
  MN: "EAST_ASIA",
  TW: "EAST_ASIA",
  HK: "EAST_ASIA",
  MO: "EAST_ASIA",

  // Southeast Asia
  VN: "SOUTHEAST_ASIA",
  TH: "SOUTHEAST_ASIA",
  LA: "SOUTHEAST_ASIA",
  KH: "SOUTHEAST_ASIA",
  MY: "SOUTHEAST_ASIA",
  SG: "SOUTHEAST_ASIA",
  ID: "SOUTHEAST_ASIA",
  PH: "SOUTHEAST_ASIA",
  MM: "SOUTHEAST_ASIA",
  BN: "SOUTHEAST_ASIA",
  TL: "SOUTHEAST_ASIA",

  // South Asia
  IN: "SOUTH_ASIA",
  PK: "SOUTH_ASIA",
  BD: "SOUTH_ASIA",
  LK: "SOUTH_ASIA",
  NP: "SOUTH_ASIA",
  BT: "SOUTH_ASIA",
  MV: "SOUTH_ASIA",
  AF: "SOUTH_ASIA",

  // Central Asia
  KZ: "CENTRAL_ASIA",
  KG: "CENTRAL_ASIA",
  TJ: "CENTRAL_ASIA",
  TM: "CENTRAL_ASIA",
  UZ: "CENTRAL_ASIA",

  // Middle East (includes Turkey for operational relevance)
  TR: "MIDDLE_EAST",
  IR: "MIDDLE_EAST",
  IQ: "MIDDLE_EAST",
  SY: "MIDDLE_EAST",
  LB: "MIDDLE_EAST",
  JO: "MIDDLE_EAST",
  IL: "MIDDLE_EAST",
  PS: "MIDDLE_EAST",
  SA: "MIDDLE_EAST",
  YE: "MIDDLE_EAST",
  OM: "MIDDLE_EAST",
  AE: "MIDDLE_EAST",
  QA: "MIDDLE_EAST",
  BH: "MIDDLE_EAST",
  KW: "MIDDLE_EAST",

  // North Africa
  EG: "NORTH_AFRICA",
  LY: "NORTH_AFRICA",
  TN: "NORTH_AFRICA",
  DZ: "NORTH_AFRICA",
  MA: "NORTH_AFRICA",
  SD: "NORTH_AFRICA",
  MR: "NORTH_AFRICA",

  // West Africa
  NG: "WEST_AFRICA",
  GH: "WEST_AFRICA",
  SN: "WEST_AFRICA",
  ML: "WEST_AFRICA",
  BF: "WEST_AFRICA",
  CI: "WEST_AFRICA",
  GN: "WEST_AFRICA",
  SL: "WEST_AFRICA",
  LR: "WEST_AFRICA",
  TG: "WEST_AFRICA",
  BJ: "WEST_AFRICA",
  NE: "WEST_AFRICA",
  CV: "WEST_AFRICA",
  GM: "WEST_AFRICA",
  GW: "WEST_AFRICA",

  // Central Africa
  CD: "CENTRAL_AFRICA",
  CG: "CENTRAL_AFRICA",
  CM: "CENTRAL_AFRICA",
  CF: "CENTRAL_AFRICA",
  TD: "CENTRAL_AFRICA",
  GA: "CENTRAL_AFRICA",
  GQ: "CENTRAL_AFRICA",
  ST: "CENTRAL_AFRICA",
  AO: "CENTRAL_AFRICA",

  // East Africa
  ET: "EAST_AFRICA",
  ER: "EAST_AFRICA",
  KE: "EAST_AFRICA",
  UG: "EAST_AFRICA",
  TZ: "EAST_AFRICA",
  RW: "EAST_AFRICA",
  BI: "EAST_AFRICA",
  DJ: "EAST_AFRICA",
  SO: "EAST_AFRICA",
  SS: "EAST_AFRICA",
  MG: "EAST_AFRICA",
  MU: "EAST_AFRICA",
  MW: "EAST_AFRICA",
  MZ: "EAST_AFRICA",
  ZM: "EAST_AFRICA",
  ZW: "EAST_AFRICA",
  KM: "EAST_AFRICA",
  SC: "EAST_AFRICA",

  // Southern Africa
  ZA: "SOUTHERN_AFRICA",
  NA: "SOUTHERN_AFRICA",
  BW: "SOUTHERN_AFRICA",
  LS: "SOUTHERN_AFRICA",
  SZ: "SOUTHERN_AFRICA",

  // Russia & Caucasus
  RU: "RUSSIA_CAUCASUS",
  AM: "RUSSIA_CAUCASUS",
  AZ: "RUSSIA_CAUCASUS",
  GE: "RUSSIA_CAUCASUS",

  // Eastern Europe
  UA: "EASTERN_EUROPE",
  BY: "EASTERN_EUROPE",
  MD: "EASTERN_EUROPE",
  PL: "EASTERN_EUROPE",
  RO: "EASTERN_EUROPE",
  BG: "EASTERN_EUROPE",
  HU: "EASTERN_EUROPE",
  CZ: "EASTERN_EUROPE",
  SK: "EASTERN_EUROPE",
  RS: "EASTERN_EUROPE",
  HR: "EASTERN_EUROPE",
  SI: "EASTERN_EUROPE",
  BA: "EASTERN_EUROPE",
  ME: "EASTERN_EUROPE",
  MK: "EASTERN_EUROPE",
  AL: "EASTERN_EUROPE",
  XK: "EASTERN_EUROPE",
  EE: "EASTERN_EUROPE",
  LV: "EASTERN_EUROPE",
  LT: "EASTERN_EUROPE",

  // Western Europe (includes Northern & Southern Europe for simplicity)
  FR: "WESTERN_EUROPE",
  DE: "WESTERN_EUROPE",
  ES: "WESTERN_EUROPE",
  IT: "WESTERN_EUROPE",
  PT: "WESTERN_EUROPE",
  NL: "WESTERN_EUROPE",
  BE: "WESTERN_EUROPE",
  LU: "WESTERN_EUROPE",
  CH: "WESTERN_EUROPE",
  AT: "WESTERN_EUROPE",
  IE: "WESTERN_EUROPE",
  IS: "WESTERN_EUROPE",
  NO: "WESTERN_EUROPE",
  SE: "WESTERN_EUROPE",
  FI: "WESTERN_EUROPE",
  DK: "WESTERN_EUROPE",
  GR: "WESTERN_EUROPE",
  CY: "WESTERN_EUROPE",
  MT: "WESTERN_EUROPE",
  VA: "WESTERN_EUROPE",
  SM: "WESTERN_EUROPE",
  MC: "WESTERN_EUROPE",
  LI: "WESTERN_EUROPE",
  AD: "WESTERN_EUROPE",

  // Oceania
  PG: "OCEANIA",
  FJ: "OCEANIA",
  SB: "OCEANIA",
  VU: "OCEANIA",
  TO: "OCEANIA",
  WS: "OCEANIA",
  KI: "OCEANIA",
  FM: "OCEANIA",
  MH: "OCEANIA",
  NR: "OCEANIA",
  PW: "OCEANIA",
  TV: "OCEANIA",

  // Caribbean
  CU: "CARIBBEAN",
  HT: "CARIBBEAN",
  DO: "CARIBBEAN",
  JM: "CARIBBEAN",
  BS: "CARIBBEAN",
  BB: "CARIBBEAN",
  TT: "CARIBBEAN",
  GD: "CARIBBEAN",
  LC: "CARIBBEAN",
  VC: "CARIBBEAN",
  AG: "CARIBBEAN",
  DM: "CARIBBEAN",
  KN: "CARIBBEAN",

  // Central America
  MX: "CENTRAL_AMERICA",
  GT: "CENTRAL_AMERICA",
  BZ: "CENTRAL_AMERICA",
  SV: "CENTRAL_AMERICA",
  HN: "CENTRAL_AMERICA",
  NI: "CENTRAL_AMERICA",
  CR: "CENTRAL_AMERICA",
  PA: "CENTRAL_AMERICA",

  // South America
  BR: "SOUTH_AMERICA",
  AR: "SOUTH_AMERICA",
  CL: "SOUTH_AMERICA",
  PE: "SOUTH_AMERICA",
  CO: "SOUTH_AMERICA",
  VE: "SOUTH_AMERICA",
  EC: "SOUTH_AMERICA",
  BO: "SOUTH_AMERICA",
  PY: "SOUTH_AMERICA",
  UY: "SOUTH_AMERICA",
  GY: "SOUTH_AMERICA",
  SR: "SOUTH_AMERICA",
  GF: "SOUTH_AMERICA",
};

/**
 * Look up the region for a given ISO 3166-1 alpha-2 code.
 * Returns null for FVEY countries (not in the map) or unknown codes.
 */
export function getRegion(iso2: string | undefined | null): Region | null {
  if (!iso2) return null;
  return COUNTRY_TO_REGION[iso2.toUpperCase()] ?? null;
}

/**
 * Predicate builder for filtering activity rows by selected regions.
 * If selected is null, returns a predicate that accepts everything (no filter).
 * If selected is an empty set, returns a predicate that accepts nothing.
 */
export function makeRegionFilter(
  selected: Set<Region> | null,
): (iso2: string) => boolean {
  if (selected === null) return () => true;
  if (selected.size === 0) return () => false;
  return (iso2: string) => {
    const region = getRegion(iso2);
    return region !== null && selected.has(region);
  };
}
