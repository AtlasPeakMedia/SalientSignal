"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import Wordmark from "@/components/Brand/Wordmark";
import Clock from "@/components/Clock";
import ErrorBoundary from "@/components/ErrorBoundary";
import ViewToggle from "@/components/Globe/ViewToggle";
import ColorLegend from "@/components/Globe/ColorLegend";
import GlobeWrapper from "@/components/Globe/GlobeWrapper";
import RegionFilter from "@/components/Globe/RegionFilter";
import HistoricalDataBanner from "@/components/HistoricalDataBanner";
import { makeRegionFilter, type Region } from "@/lib/country-regions";
import type {
  CountryActivity,
  CoordinationArc,
  TrendingTheme,
} from "@/lib/types";

type ViewMode = "DOMESTIC" | "INTERNATIONAL" | "BOTH";

interface Props {
  countryActivity: CountryActivity[];
  coordinationArcs: CoordinationArc[];
  trendingThemes: TrendingTheme[];
  isDummy: boolean;
  latestDate: string | null;
}

export default function HomePageClient({
  countryActivity,
  coordinationArcs,
  trendingThemes,
  isDummy,
  latestDate,
}: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>("BOTH");
  // Region filter: null = "all regions", explicit set = "only these regions".
  // Countries outside the selected regions fall out of the dataset passed to
  // the globe and the top-movers panel, so the globe renders them as neutral
  // (the same fallback used for unmonitored countries).
  const [selectedRegions, setSelectedRegions] = useState<Set<Region> | null>(
    null,
  );

  // Apply the region filter to the raw country list before anything else
  // consumes it. Top movers, globe polygons, trending themes, and the footer
  // "N countries with data" count all read from this filtered set.
  const filteredCountryActivity = useMemo(() => {
    const predicate = makeRegionFilter(selectedRegions);
    return countryActivity.filter((c) => predicate(c.iso2));
  }, [countryActivity, selectedRegions]);

  // Top 5 most-elevated countries (by max |z-score| across audience types).
  // After the region filter, this reflects only the selected regions.
  const topMovers = useMemo(() => {
    const sorted = [...filteredCountryActivity].sort((a, b) => {
      const aZ = Math.max(
        Math.abs(a.domestic.zScore),
        Math.abs(a.international.zScore),
      );
      const bZ = Math.max(
        Math.abs(b.domestic.zScore),
        Math.abs(b.international.zScore),
      );
      if (bZ !== aZ) return bZ - aZ;
      const aCount = a.domestic.today + a.international.today;
      const bCount = b.domestic.today + b.international.today;
      return bCount - aCount;
    });
    return sorted.slice(0, 5);
  }, [filteredCountryActivity]);

  // B7 Firefox fix: NEVER call new Date() here without an explicit ISO date.
  // When latestDate is missing (shouldn't happen for live data), fall back to
  // a generic label instead of a wall-clock Date() — which would hydration-
  // mismatch on SSR vs client.
  const dateLabel = latestDate
    ? new Date(latestDate + "T00:00:00Z").toLocaleDateString("en-US", {
        weekday: "long",
        month: "long",
        day: "numeric",
        timeZone: "UTC",
      })
    : "the most recent day";

  // D16: Post-backfill — the 21-day cold-start period is gone. The banner
  // now shows for two reasons: (a) dummy data fixture is active, or (b)
  // latestDate is stale relative to today (pipeline outage).
  //
  // latestDate is a YYYY-MM-DD string from the server. We treat anything
  // older than 2 days as stale to account for timezone + hourly cron cadence.
  const isStale = (() => {
    if (isDummy || !latestDate) return false;
    try {
      const latest = new Date(latestDate + "T00:00:00Z").getTime();
      const now = Date.now();
      const twoDaysMs = 2 * 24 * 60 * 60 * 1000;
      return now - latest > twoDaysMs;
    } catch {
      return false;
    }
  })();

  const showBanner = isDummy || isStale;
  const headerBadge = isDummy ? "DEMO" : "LIVE";

  return (
    <main className="min-h-screen">
      {/* Header */}
      <header className="border-b border-bg-divider">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
          <Wordmark />
          <nav className="flex items-center gap-6 text-sm text-text-secondary">
            <Link
              href="/methodology"
              className="hover:text-text-body transition-colors"
            >
              Methodology
            </Link>
            <Link
              href="/about"
              className="hover:text-text-body transition-colors"
            >
              About
            </Link>
            <span className="text-mono text-xs px-2 py-1 rounded border border-bg-divider">
              {headerBadge}
            </span>
          </nav>
        </div>
      </header>

      {/* Historical-data / stale-data / dummy-preview banner (D16) */}
      <HistoricalDataBanner show={showBanner} isDummy={isDummy} isStale={isStale} />

      {/* Globe controls */}
      <div className="max-w-[1400px] mx-auto px-6 pt-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <h1 className="text-sm text-text-secondary">
            <span className="text-text-body font-medium">
              {isDummy ? "Demo activity" : "Today's activity"}
            </span>
            <span className="mx-2 text-bg-divider">•</span>
            <span className="text-mono">{dateLabel}</span>
            {selectedRegions !== null && (
              <>
                <span className="mx-2 text-bg-divider">•</span>
                <span className="text-mono text-accent-tealBright">
                  {filteredCountryActivity.length} of {countryActivity.length}{" "}
                  countries
                </span>
              </>
            )}
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <ColorLegend />
          <ViewToggle value={viewMode} onChange={setViewMode} />
          <RegionFilter
            selected={selectedRegions}
            onChange={setSelectedRegions}
          />
        </div>
      </div>

      {/* Globe */}
      <div className="relative">
        <ErrorBoundary label="Globe">
          <GlobeWrapper
            viewMode={viewMode}
            countryActivity={filteredCountryActivity}
            coordinationArcs={coordinationArcs}
          />
        </ErrorBoundary>
      </div>

      {/* Bottom panel — top movers + themes */}
      <section className="max-w-[1400px] mx-auto px-6 py-8 grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Top movers */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-text-body uppercase tracking-wider">
              {isDummy ? "Biggest Movers Today" : "Most Active Countries"}
            </h2>
            <span className="text-xs text-text-secondary text-mono">
              by z-score
            </span>
          </div>
          {topMovers.length === 0 ? (
            <div className="text-sm text-text-secondary italic py-8 text-center">
              No country activity yet. Pipeline is warming up.
            </div>
          ) : (
            <ul className="space-y-3">
              {topMovers.map((country) => {
                const domAbs = Math.abs(country.domestic.zScore);
                const intlAbs = Math.abs(country.international.zScore);
                const moreNotable = domAbs > intlAbs ? country.domestic : country.international;
                const audience = domAbs > intlAbs ? "DOMESTIC" : "INTERNATIONAL";
                const totalCount = country.domestic.today + country.international.today;
                return (
                  <li key={country.iso2}>
                    <Link
                      href={`/country/${country.iso2}`}
                      className="flex items-center justify-between p-3 rounded-md hover:bg-bg-base/50 transition-colors group"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">{country.flag}</span>
                        <div>
                          <div className="text-sm font-medium text-text-body group-hover:text-white transition-colors">
                            {country.name}
                          </div>
                          <div className="text-xs text-text-secondary text-mono">
                            {audience.toLowerCase()}
                            {moreNotable.zScore !== 0 && (
                              <> • z-score {moreNotable.zScore}</>
                            )}
                            {country.coldStart && <> • cold start</>}
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-mono text-sm text-amber-400">
                          {totalCount} {totalCount === 1 ? "article" : "articles"}
                        </div>
                        <div className="text-xs text-text-secondary">
                          dom {country.domestic.today} • intl {country.international.today}
                        </div>
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Trending themes */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-text-body uppercase tracking-wider">
              Trending Themes
            </h2>
            <span className="text-xs text-text-secondary text-mono">
              cross-country
            </span>
          </div>
          {trendingThemes.length === 0 ? (
            <div className="text-sm text-text-secondary italic py-8 text-center">
              Theme extraction comes online once GDELT populates the theme field.
            </div>
          ) : (
            <ul className="space-y-2">
              {trendingThemes.map((theme) => {
                const isUp = theme.change.startsWith("+");
                return (
                  <li
                    key={theme.theme}
                    className="flex items-center justify-between p-2.5 rounded-md hover:bg-bg-base/50 transition-colors"
                  >
                    <span className="text-sm text-text-body">{theme.label}</span>
                    <div className="flex items-center gap-3 text-mono text-xs">
                      <span className="text-text-secondary">{theme.count}</span>
                      {theme.change && (
                        <span
                          className={
                            isUp
                              ? "text-accent-tealBright"
                              : "text-text-secondary"
                          }
                        >
                          {theme.change}
                        </span>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </section>

      {/* Footer */}
      <footer className="max-w-[1400px] mx-auto px-6 py-6 text-xs text-text-secondary border-t border-bg-divider">
        <div className="flex items-center justify-end">
          <span className="text-mono">
            {isDummy ? "DEMO DATA" : "LIVE DATA"} · <Clock />
          </span>
        </div>
      </footer>
    </main>
  );
}
