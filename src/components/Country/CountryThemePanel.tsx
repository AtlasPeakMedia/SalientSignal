/**
 * CountryThemePanel — the SCAME dashboard V1 theme browser.
 *
 * Session 31 product: the user clicks a country and sees "what were the
 * main issues being discussed by state media for this country in X month
 * of X year, split by DOMESTIC vs INTERNATIONAL audience". This component
 * renders that view.
 *
 * Design:
 *   - Two columns side-by-side: DOMESTIC (left) | INTERNATIONAL (right).
 *     These are NEVER conflated — the audience split is the core SCAME
 *     innovation. If a country has no DOMESTIC themes for the selected
 *     period (e.g. Iran, where all outlets in our set are English-language
 *     editions classified INTERNATIONAL), that column shows an empty state
 *     rather than falling back to the other audience.
 *   - Period picker at top: monthly tabs. User picks a month, both columns
 *     refresh. Weekly and daily periods are behind the same picker but
 *     hidden until the backfill for those granularities exists.
 *   - Each theme renders as a sized pill. Font size scales with the
 *     theme's `share` (0..1) of the bucket — from ~0.75rem to ~1.75rem.
 *     Pill color tints based on avgTone: red for hostile (<-3), amber
 *     for negative (-3..-1), neutral for flat (-1..+1), teal for positive.
 *   - Clicking a pill opens a modal with the top articles mentioning that
 *     theme (Phase V2 — not implemented in V1, pill is non-clickable for now).
 *
 * Empty states:
 *   - No theme data at all (schema v3 not applied OR table not populated):
 *     shows a one-liner "Theme analysis coming soon — 15 months of
 *     historical themes are being ingested." No error, no crash.
 *   - No DOMESTIC themes for this period but INTERNATIONAL has data: the
 *     DOMESTIC column shows "No domestic-facing outlets captured in this
 *     period" and the user still gets the INTL view.
 *
 * Performance: this is a pure client component rendering already-fetched
 * data from a server component parent. No data fetching here. No state
 * beyond the selected period.
 */
"use client";

import { useMemo, useState } from "react";
import type { CountryThemeRow } from "@/lib/types";

interface Props {
  /** Pre-fetched theme rows for this country (all audiences, all periods). */
  themes: CountryThemeRow[];
  countryName: string;
}

/**
 * Group theme rows by (audience_type, period_start). Returns a Map keyed
 * by `${audience}__${periodStart}` for cheap lookup by the picker + render.
 */
function groupThemes(
  rows: CountryThemeRow[],
): Map<string, CountryThemeRow[]> {
  const out = new Map<string, CountryThemeRow[]>();
  for (const row of rows) {
    const key = `${row.audienceType}__${row.periodStart}`;
    const existing = out.get(key);
    if (existing) {
      existing.push(row);
    } else {
      out.set(key, [row]);
    }
  }
  // Ensure each bucket's themes are sorted by article_count desc for render
  for (const themes of out.values()) {
    themes.sort((a, b) => b.articleCount - a.articleCount);
  }
  return out;
}

/** Unique sorted period_start values, newest first, for the picker. */
function uniquePeriods(rows: CountryThemeRow[]): string[] {
  const set = new Set<string>();
  for (const row of rows) set.add(row.periodStart);
  return Array.from(set).sort((a, b) => (a < b ? 1 : -1));
}

function formatPeriodLabel(periodStart: string): string {
  // periodStart is "YYYY-MM-DD". We show it as "Month YYYY" (monthly) or
  // "Mon D" (weekly/daily fallback).
  try {
    const d = new Date(`${periodStart}T00:00:00Z`);
    return d.toLocaleDateString("en-US", {
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    });
  } catch {
    return periodStart;
  }
}

/**
 * Map avgTone to a color class.
 *   avgTone < -3   → red-leaning    (hostile/crisis framing)
 *   -3 .. -1       → amber          (negative)
 *   -1 .. +1       → neutral        (descriptive)
 *   +1 .. +3       → teal-ish       (positive)
 *   > +3           → green-teal     (celebratory)
 *   null           → neutral
 */
function toneClass(avgTone: number | null): string {
  if (avgTone === null) return "bg-bg-raised/60 border-bg-divider text-text-body";
  if (avgTone < -3) return "bg-accent-red/10 border-accent-red/40 text-accent-red";
  if (avgTone < -1) return "bg-accent-amber/10 border-accent-amber/40 text-accent-amber";
  if (avgTone <= 1) return "bg-bg-raised/60 border-bg-divider text-text-body";
  if (avgTone <= 3) return "bg-accent-tealBright/10 border-accent-tealBright/40 text-accent-tealBright";
  return "bg-accent-tealBright/15 border-accent-tealBright/60 text-accent-tealBright";
}

/**
 * Size a pill proportional to its share of the bucket. Clamp to a sane
 * range — we don't want the biggest theme 6x the text height.
 */
function pillSizeRem(share: number): number {
  const minRem = 0.75;
  const maxRem = 1.5;
  // Cap share at 0.5 so a 100%-coverage theme isn't absurdly large
  const capped = Math.min(share, 0.5);
  return minRem + (maxRem - minRem) * (capped / 0.5);
}

export default function CountryThemePanel({ themes, countryName }: Props) {
  const periods = useMemo(() => uniquePeriods(themes), [themes]);
  const grouped = useMemo(() => groupThemes(themes), [themes]);
  const [selectedPeriod, setSelectedPeriod] = useState<string | null>(
    periods[0] ?? null,
  );

  // Empty state: no data at all
  if (themes.length === 0) {
    return (
      <section className="max-w-[1400px] mx-auto px-6 mb-8">
        <div className="card p-6">
          <div className="flex items-start justify-between mb-4">
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
              Theme analysis
            </h2>
            <span className="text-xs text-text-secondary text-mono">
              SCAME dashboard
            </span>
          </div>
          <p className="text-sm text-text-body leading-relaxed">
            15 months of historical theme data are being ingested from
            GDELT&apos;s Global Knowledge Graph. Once the backfill completes
            and the country_theme_monthly table is populated, this panel
            will show {countryName}&apos;s top themes by month with a
            DOMESTIC vs INTERNATIONAL audience split.
          </p>
          <p className="text-xs text-text-secondary mt-3">
            The audience split is deliberate — we never conflate what a
            country&apos;s state media tells its own population with what
            it tells the world.
          </p>
        </div>
      </section>
    );
  }

  const domesticKey = `DOMESTIC__${selectedPeriod ?? ""}`;
  const intlKey = `INTERNATIONAL__${selectedPeriod ?? ""}`;
  const domesticThemes = grouped.get(domesticKey) ?? [];
  const intlThemes = grouped.get(intlKey) ?? [];

  return (
    <section className="max-w-[1400px] mx-auto px-6 mb-8">
      <div className="card p-6">
        {/* Header + period picker */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-5 pb-4 border-b border-bg-divider">
          <div>
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider mb-1">
              Theme analysis — {countryName}
            </h2>
            <p className="text-xs text-text-secondary">
              Top themes mentioned in state media, split by intended audience.
              Size = share of the period&apos;s articles mentioning that
              theme. Color = average tone (red = hostile, amber = negative,
              teal = positive).
            </p>
          </div>
          {periods.length > 0 && (
            <div
              className="flex flex-wrap items-center gap-1 text-xs"
              role="tablist"
              aria-label="Select time period"
            >
              {periods.slice(0, 18).map((p) => {
                const isSelected = p === selectedPeriod;
                return (
                  <button
                    key={p}
                    role="tab"
                    aria-selected={isSelected}
                    onClick={() => setSelectedPeriod(p)}
                    className={`px-3 py-1.5 rounded-md border text-mono transition-colors ${
                      isSelected
                        ? "bg-accent-tealBright/15 border-accent-tealBright text-accent-tealBright"
                        : "bg-bg-raised/40 border-bg-divider text-text-secondary hover:text-text-body hover:border-bg-divider"
                    }`}
                  >
                    {formatPeriodLabel(p)}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Two-column audience split */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ThemeColumn
            label="Domestic audience"
            sublabel="What state media tells its own population"
            themes={domesticThemes}
            emptyNote={
              intlThemes.length > 0
                ? "No domestic-facing outlets captured for this country in this period."
                : "No data for this period."
            }
          />
          <ThemeColumn
            label="International audience"
            sublabel="What state media tells the world (non-native languages, foreign-facing outlets)"
            themes={intlThemes}
            emptyNote={
              domesticThemes.length > 0
                ? "No international-facing outlets captured in this period."
                : "No data for this period."
            }
          />
        </div>

        {/* Footer with bucket totals + provenance */}
        <div className="mt-5 pt-4 border-t border-bg-divider flex flex-wrap items-center justify-between gap-2 text-xs text-text-secondary">
          <span>
            {selectedPeriod && (
              <>
                Period: <span className="text-mono">{formatPeriodLabel(selectedPeriod)}</span>
                {" · "}
                <span className="text-mono">
                  {domesticThemes.reduce((sum, t) => sum + t.articleCount, 0) +
                    intlThemes.reduce((sum, t) => sum + t.articleCount, 0)}
                </span>{" "}
                theme mentions across{" "}
                {(domesticThemes[0]?.bucketTotal ?? 0) +
                  (intlThemes[0]?.bucketTotal ?? 0)}{" "}
                unique articles
              </>
            )}
          </span>
          <span>
            Source: GDELT Global Knowledge Graph 2.0
          </span>
        </div>
      </div>
    </section>
  );
}

interface ColumnProps {
  label: string;
  sublabel: string;
  themes: CountryThemeRow[];
  emptyNote: string;
}

function ThemeColumn({ label, sublabel, themes, emptyNote }: ColumnProps) {
  return (
    <div>
      <div className="mb-3">
        <h3 className="text-xs font-semibold text-white uppercase tracking-wider mb-1">
          {label}
        </h3>
        <p className="text-xs text-text-secondary">{sublabel}</p>
      </div>
      {themes.length === 0 ? (
        <div className="text-xs text-text-secondary italic py-6 px-3 rounded border border-bg-divider bg-bg-raised/30">
          {emptyNote}
        </div>
      ) : (
        <div className="flex flex-wrap gap-2 items-baseline">
          {themes.slice(0, 40).map((t) => {
            const fontRem = pillSizeRem(t.share);
            const sharePct = Math.round(t.share * 100);
            const toneLabel =
              t.avgTone === null
                ? ""
                : ` · avg tone ${t.avgTone.toFixed(1)}`;
            return (
              <span
                key={`${t.theme}-${t.periodStart}`}
                title={`${t.articleCount} of ${t.bucketTotal} articles (${sharePct}%)${toneLabel}`}
                className={`inline-flex items-center rounded-full px-3 py-1 border ${toneClass(
                  t.avgTone,
                )}`}
                style={{ fontSize: `${fontRem}rem`, lineHeight: 1.3 }}
              >
                {t.label}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}
