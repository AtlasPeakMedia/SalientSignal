/**
 * Unified data layer for the SalientSignal frontend.
 *
 * Every page and API route reads through these helpers instead of importing
 * from dummy-data directly. Under the hood, each helper routes to either
 * the live Supabase pipeline or the static dummy fixture based on the
 * NEXT_PUBLIC_USE_DUMMY_DATA env flag (and auto-falls-back to dummy if
 * Supabase credentials are missing).
 *
 * Flag semantics:
 *   NEXT_PUBLIC_USE_DUMMY_DATA=true   → always dummy (safe default for preview)
 *   NEXT_PUBLIC_USE_DUMMY_DATA=false  → real data (required for prod)
 *   unset                             → real data IF credentials exist, else dummy
 *
 * All server-side data fetches (queries to Supabase) happen here. The Globe,
 * home page, country page, and API routes never touch the Supabase client
 * directly — this module is the single adapter layer.
 */

import "server-only";
import { getServerSupabase, hasSupabaseCredentials } from "./supabase";
import { getCountryMeta } from "./countries-meta";
import {
  COUNTRY_ACTIVITY,
  COORDINATION_ARCS,
  TRENDING_THEMES,
  HEADLINES,
} from "./dummy-data";
import type {
  AudienceActivity,
  CountryActivity,
  CoordinationArc,
  DeviationLevel,
  Headline,
  TrendingTheme,
} from "./types";

// ============================================================================
// Feature flag
// ============================================================================

export function isUsingDummyData(): boolean {
  const flag = process.env.NEXT_PUBLIC_USE_DUMMY_DATA;
  if (flag === "true") return true;
  if (flag === "false") return false;
  // Default: real data if credentials exist, else dummy fallback
  return !hasSupabaseCredentials();
}

// ============================================================================
// DB row shapes (internal — do not export)
// ============================================================================

interface DbCountryActivityRow {
  country: string;
  date: string;
  audience_type: string;
  today_count: number;
  baseline_mean: number | null;
  baseline_std: number | null;
  deviation_ratio: number | null;
  z_score: number | null;
  level: string | null;
  confidence: string | null;
  cold_start: boolean | null;
  top_outlets: unknown;
  top_themes: unknown;
}

interface DbArticleRow {
  url: string;
  title_original: string | null;
  source_domain: string;
  source_country: string;
  source_language: string | null;
  audience_type: string;
  gdelt_themes: string[] | null;
  pub_date: string;
}

interface DbOutletRow {
  domain: string;
  outlet_name: string;
}

// ============================================================================
// Mapping helpers
// ============================================================================

const VALID_LEVELS: ReadonlySet<DeviationLevel> = new Set<DeviationLevel>([
  "deepBlue",
  "steelBlue",
  "coolGray",
  "neutral",
  "amber",
  "orange",
  "red",
]);

function parseLevel(raw: string | null | undefined): DeviationLevel {
  if (raw && VALID_LEVELS.has(raw as DeviationLevel)) return raw as DeviationLevel;
  return "neutral";
}

function round(n: number | null | undefined, places = 2): number {
  if (n === null || n === undefined || Number.isNaN(n)) return 0;
  const m = 10 ** places;
  return Math.round(n * m) / m;
}

function emptyAudience(): AudienceActivity {
  return {
    today: 0,
    baseline: 0,
    ratio: 1,
    zScore: 0,
    level: "neutral",
    confidence: "LOW",
    coldStart: true,
    topOutlets: [],
    topThemes: [],
  };
}

/** Coerce a JSONB top_outlets field into the normalized array shape. */
function parseTopOutlets(raw: unknown): Array<{ domain: string; count: number }> {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const obj = item as Record<string, unknown>;
      const domain = typeof obj.domain === "string" ? obj.domain : null;
      const count = typeof obj.count === "number" ? obj.count : 0;
      if (!domain) return null;
      return { domain, count };
    })
    .filter((v): v is { domain: string; count: number } => v !== null)
    .slice(0, 5);
}

/**
 * Coerce a JSONB top_themes field into the normalized array shape.
 * DB stores as either an object `{theme: count}` or an array `[{theme, count}]`.
 */
function parseTopThemes(raw: unknown): Array<{ theme: string; count: number }> {
  if (Array.isArray(raw)) {
    return raw
      .map((item) => {
        if (!item || typeof item !== "object") return null;
        const obj = item as Record<string, unknown>;
        const theme = typeof obj.theme === "string" ? obj.theme : null;
        const count = typeof obj.count === "number" ? obj.count : 0;
        if (!theme) return null;
        return { theme, count };
      })
      .filter((v): v is { theme: string; count: number } => v !== null)
      .slice(0, 10);
  }
  if (raw && typeof raw === "object") {
    return Object.entries(raw as Record<string, unknown>)
      .filter(([, count]) => typeof count === "number")
      .map(([theme, count]) => ({ theme, count: count as number }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
  }
  return [];
}

function rowToAudience(row: DbCountryActivityRow): AudienceActivity {
  const today = row.today_count ?? 0;
  const baseline = Math.round(row.baseline_mean ?? 0);
  const ratio = round(row.deviation_ratio, 2);
  const zScore = round(row.z_score, 1);
  return {
    today,
    baseline,
    ratio,
    zScore,
    level: parseLevel(row.level),
    confidence: (row.confidence as AudienceActivity["confidence"]) ?? "LOW",
    coldStart: row.cold_start ?? false,
    topOutlets: parseTopOutlets(row.top_outlets),
    topThemes: parseTopThemes(row.top_themes),
  };
}

// ============================================================================
// Public data helpers
// ============================================================================

/**
 * All countries with activity for the most recent date that has data.
 * Returns an empty array if Supabase is unreachable — callers can show a banner.
 */
export async function getAllCountryActivity(): Promise<CountryActivity[]> {
  if (isUsingDummyData()) {
    console.log("[data] isUsingDummyData() = true, returning fixture");
    return COUNTRY_ACTIVITY;
  }

  const client = getServerSupabase();
  if (!client) {
    console.warn(
      "[data] getServerSupabase() returned null — credentials missing. " +
        "Check SUPABASE_URL and SUPABASE_SECRET_KEY env vars. Falling back to dummy.",
    );
    return COUNTRY_ACTIVITY;
  }

  // Find the most recent date with data.
  const { data: latestRow, error: latestErr } = await client
    .from("country_activity")
    .select("date")
    .order("date", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (latestErr) {
    console.error(
      "[data] Supabase error fetching latest country_activity date:",
      JSON.stringify({
        message: latestErr.message,
        code: latestErr.code,
        details: latestErr.details,
        hint: latestErr.hint,
      }),
    );
    return COUNTRY_ACTIVITY;
  }
  if (!latestRow?.date) {
    console.warn(
      "[data] country_activity table is empty (no rows for any date). " +
        "Pipeline may not have run yet. Falling back to dummy.",
    );
    return COUNTRY_ACTIVITY;
  }

  console.log(
    `[data] Found latest country_activity date: ${latestRow.date}. Fetching all rows for that date...`,
  );

  const { data: rows, error: rowsErr } = await client
    .from("country_activity")
    .select(
      "country, date, audience_type, today_count, baseline_mean, baseline_std, deviation_ratio, z_score, level, confidence, cold_start, top_outlets, top_themes",
    )
    .eq("date", latestRow.date);

  if (rowsErr) {
    console.error(
      "[data] Supabase error fetching country_activity rows:",
      JSON.stringify({
        message: rowsErr.message,
        code: rowsErr.code,
        details: rowsErr.details,
        hint: rowsErr.hint,
      }),
    );
    return COUNTRY_ACTIVITY;
  }
  if (!rows || rows.length === 0) {
    console.warn(
      `[data] Zero rows returned for date ${latestRow.date}. Falling back to dummy.`,
    );
    return COUNTRY_ACTIVITY;
  }

  console.log(`[data] Loaded ${rows.length} country_activity rows for ${latestRow.date}`);

  // Group rows by country, merge DOMESTIC + INTERNATIONAL into one object.
  type AudienceBucket = {
    domestic?: DbCountryActivityRow;
    international?: DbCountryActivityRow;
  };
  const grouped = new Map<string, AudienceBucket>();

  for (const row of rows as DbCountryActivityRow[]) {
    const iso = row.country?.toUpperCase();
    if (!iso || iso.length !== 2) continue;
    const bucket = grouped.get(iso) ?? {};
    if (row.audience_type === "DOMESTIC") {
      bucket.domestic = row;
    } else if (
      row.audience_type === "INTERNATIONAL" ||
      row.audience_type === "DIASPORA"
    ) {
      // Merge DIASPORA into INTERNATIONAL for display
      bucket.international = row;
    }
    grouped.set(iso, bucket);
  }

  const out: CountryActivity[] = [];
  for (const [iso, bucket] of grouped) {
    const meta = getCountryMeta(iso);
    if (!meta) continue; // Skip codes we don't have display metadata for

    const domestic = bucket.domestic ? rowToAudience(bucket.domestic) : emptyAudience();
    const international = bucket.international
      ? rowToAudience(bucket.international)
      : emptyAudience();

    out.push({
      iso2: iso,
      name: meta.name,
      flag: meta.flag,
      region: meta.region,
      domestic,
      international,
      coldStart: Boolean(domestic.coldStart || international.coldStart),
    });
  }

  return out;
}

/**
 * One country's activity for the most recent date.
 * Returns null if the country has never had data ingested.
 */
export async function getCountryActivityByCode(
  iso2: string,
): Promise<CountryActivity | null> {
  const normalized = iso2.toUpperCase();

  if (isUsingDummyData()) {
    return COUNTRY_ACTIVITY.find((c) => c.iso2 === normalized) ?? null;
  }

  const all = await getAllCountryActivity();
  return all.find((c) => c.iso2 === normalized) ?? null;
}

/**
 * Recent headlines for a country, joined with outlet names.
 * Returns at most 20 rows sorted by publication time desc.
 */
export async function getCountryHeadlines(iso2: string): Promise<Headline[]> {
  const normalized = iso2.toUpperCase();

  if (isUsingDummyData()) {
    return HEADLINES[normalized] ?? [];
  }

  const client = getServerSupabase();
  if (!client) return HEADLINES[normalized] ?? [];

  const { data: articles, error: articlesErr } = await client
    .from("articles")
    .select(
      "url, title_original, source_domain, source_country, source_language, audience_type, gdelt_themes, pub_date",
    )
    .eq("source_country", normalized)
    .order("pub_date", { ascending: false })
    .limit(20);

  if (articlesErr || !articles || articles.length === 0) {
    return [];
  }

  // Resolve outlet_name via outlet_classification (pre-fetch for all relevant domains).
  const domains = Array.from(new Set(articles.map((a) => (a as DbArticleRow).source_domain)));
  const { data: outlets } = await client
    .from("outlet_classification")
    .select("domain, outlet_name")
    .in("domain", domains);

  const outletNameByDomain = new Map<string, string>(
    ((outlets ?? []) as DbOutletRow[]).map((o) => [o.domain, o.outlet_name]),
  );

  return (articles as DbArticleRow[]).map((a) => {
    const domain = a.source_domain;
    // Subdomain walk-up for display name
    let outletName = outletNameByDomain.get(domain);
    if (!outletName) {
      const parts = domain.split(".");
      for (let i = 1; i < parts.length; i++) {
        const parent = parts.slice(i).join(".");
        const name = outletNameByDomain.get(parent);
        if (name) {
          outletName = name;
          break;
        }
      }
    }
    const audienceType = (
      a.audience_type === "DOMESTIC" || a.audience_type === "INTERNATIONAL"
        ? a.audience_type
        : "INTERNATIONAL"
    ) as "DOMESTIC" | "INTERNATIONAL";

    return {
      outlet: outletName ?? domain,
      outletLanguage: a.source_language ?? "",
      audienceType,
      title: a.title_original ?? "(untitled)",
      publishedAt: a.pub_date,
      url: a.url,
      themes: Array.isArray(a.gdelt_themes) ? a.gdelt_themes.slice(0, 6) : [],
    } as Headline;
  });
}

/**
 * Coordination arcs for the most recent date.
 * Will be empty during the cold start period — that's expected.
 */
export async function getCoordinationArcs(): Promise<CoordinationArc[]> {
  if (isUsingDummyData()) {
    return COORDINATION_ARCS;
  }

  const client = getServerSupabase();
  if (!client) return [];

  const { data: latestRow } = await client
    .from("coordination_events")
    .select("date")
    .order("date", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (!latestRow?.date) return [];

  const { data: events } = await client
    .from("coordination_events")
    .select("theme, countries, score, date")
    .eq("date", latestRow.date);

  if (!events) return [];

  // Expand each multi-country event into pairwise arcs for rendering.
  const arcs: CoordinationArc[] = [];
  for (const event of events) {
    const countries = (event.countries ?? []) as string[];
    if (countries.length < 2) continue;
    for (let i = 0; i < countries.length; i++) {
      for (let j = i + 1; j < countries.length; j++) {
        const startIso = countries[i].toUpperCase();
        const endIso = countries[j].toUpperCase();
        const startMeta = getCountryMeta(startIso);
        const endMeta = getCountryMeta(endIso);
        if (!startMeta || !endMeta) continue;
        arcs.push({
          startIso,
          endIso,
          theme: event.theme,
          themeLabel: event.theme.replace(/_/g, " ").toLowerCase(),
          countries,
          score: event.score ?? 0.5,
          startCountry: startMeta.name,
          endCountry: endMeta.name,
        });
      }
    }
  }

  return arcs;
}

/**
 * Top trending themes across all countries for the most recent date.
 * Computed client-side (TypeScript) from the top_themes JSONB on each country_activity row.
 */
export async function getTrendingThemes(): Promise<TrendingTheme[]> {
  if (isUsingDummyData()) {
    return TRENDING_THEMES;
  }

  const countries = await getAllCountryActivity();
  if (countries.length === 0) return [];

  // Aggregate theme counts across all countries / both audience types.
  const byTheme = new Map<string, number>();
  for (const c of countries) {
    for (const t of c.domestic.topThemes ?? []) {
      byTheme.set(t.theme, (byTheme.get(t.theme) ?? 0) + t.count);
    }
    for (const t of c.international.topThemes ?? []) {
      byTheme.set(t.theme, (byTheme.get(t.theme) ?? 0) + t.count);
    }
  }

  return Array.from(byTheme.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([theme, count]) => ({
      theme,
      label: prettifyTheme(theme),
      count,
      change: "", // Phase 4 MVP: skip the WoW delta column, return empty
    }));
}

function prettifyTheme(theme: string): string {
  return theme
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
