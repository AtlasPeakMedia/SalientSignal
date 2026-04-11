/**
 * Shared types for the frontend — used by both the dummy fixture
 * and the real Supabase data layer. Keeps one source of truth.
 */

export type AudienceType = "DOMESTIC" | "INTERNATIONAL" | "DIASPORA";

export type DeviationLevel =
  | "deepBlue"
  | "steelBlue"
  | "coolGray"
  | "neutral"
  | "amber"
  | "orange"
  | "red";

export type Confidence = "LOW" | "MEDIUM" | "HIGH";

/** Per-audience activity block (half of a country row). */
export interface AudienceActivity {
  today: number;
  baseline: number;
  ratio: number;
  zScore: number;
  level: DeviationLevel;
  confidence?: Confidence;
  coldStart?: boolean;
  topOutlets?: Array<{ domain: string; count: number }>;
  topThemes?: Array<{ theme: string; count: number }>;
}

/** One country's activity for the current day, both audience columns merged. */
export interface CountryActivity {
  iso2: string; // ISO 3166-1 alpha-2
  name: string;
  flag: string; // Emoji
  region: string;
  domestic: AudienceActivity;
  international: AudienceActivity;
  /** True if EITHER audience is still in the cold start window. */
  coldStart?: boolean;
  /**
   * ISO YYYY-MM-DD of the day this activity row represents. For live data
   * this is the most recent ingested date from country_activity; for dummy
   * data it's a stable fixture date. NEVER use ``new Date()`` to derive a
   * label for this field on the client — that causes SSR/client hydration
   * mismatches (see B7 Firefox fix). Always pass this through from the
   * server component.
   */
  latestDate?: string;
}

/** One headline row used on the country detail page. */
export interface Headline {
  outlet: string;
  outletLanguage: string;
  audienceType: AudienceType;
  title: string;
  publishedAt: string; // ISO timestamp
  url: string;
  themes: string[];
}

/** Coordination arc drawn on the globe between two countries pushing a shared theme. */
export interface CoordinationArc {
  startIso: string;
  endIso: string;
  theme: string;
  themeLabel: string;
  countries: string[];
  score: number; // 0.0 - 1.0
  startCountry: string;
  endCountry: string;
}

/** Trending theme row in the home page panel. */
export interface TrendingTheme {
  theme: string;
  label: string;
  count: number;
  change: string;
}

/**
 * One aggregated theme row for the SCAME dashboard.
 *
 * Comes from the `country_theme_{monthly|weekly|daily}` tables, populated
 * by the GDELT GKG 2.0 bulk-file ingestion pipeline (Session 31). Each row
 * represents "in bucket (country, audience, period), the theme `theme`
 * appeared in `articleCount` articles out of `bucketTotal` total, which
 * is `share` of the bucket; the average tone of those articles was
 * `avgTone`."
 *
 * The dashboard queries this grouped by country + audience + period to
 * render word clouds and narrative breakdowns. DOMESTIC vs INTERNATIONAL
 * is NEVER conflated — that's the core product innovation.
 */
export interface CountryThemeRow {
  country: string;
  audienceType: AudienceType;
  periodStart: string; // YYYY-MM-DD
  periodEnd: string; // YYYY-MM-DD
  theme: string;
  /** Prettified human-readable label (e.g. "Armed Conflict" for ARMEDCONFLICT) */
  label: string;
  articleCount: number;
  bucketTotal: number;
  share: number; // 0..1
  avgTone: number | null; // -10..+10, null if no tone data
}

export type ThemePeriod = "monthly" | "weekly" | "daily";
