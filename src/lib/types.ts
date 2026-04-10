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
