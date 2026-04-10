"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import Wordmark from "@/components/Brand/Wordmark";
import ViewToggle from "@/components/Globe/ViewToggle";
import ColorLegend from "@/components/Globe/ColorLegend";
import GlobeWrapper from "@/components/Globe/GlobeWrapper";
import ColdStartBanner from "@/components/ColdStartBanner";
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
  coldStartCount: number;
}

export default function HomePageClient({
  countryActivity,
  coordinationArcs,
  trendingThemes,
  isDummy,
  latestDate,
  coldStartCount,
}: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>("BOTH");

  // Top 5 most-elevated countries (by max |z-score| across audience types).
  // During cold start z-scores are all 0, so we fall back to raw article count.
  const topMovers = useMemo(() => {
    const sorted = [...countryActivity].sort((a, b) => {
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
  }, [countryActivity]);

  const dateLabel = latestDate
    ? new Date(latestDate + "T00:00:00Z").toLocaleDateString("en-US", {
        weekday: "long",
        month: "long",
        day: "numeric",
        timeZone: "UTC",
      })
    : new Date().toLocaleDateString("en-US", {
        weekday: "long",
        month: "long",
        day: "numeric",
      });

  const showColdStart = coldStartCount > 0 || isDummy;
  const headerBadge = isDummy ? "DEMO" : coldStartCount > 0 ? "COLD START" : "LIVE";

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

      {/* Cold start banner */}
      <ColdStartBanner show={showColdStart && !isDummy} />

      {/* Globe controls */}
      <div className="max-w-[1400px] mx-auto px-6 pt-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <h1 className="text-sm text-text-secondary">
            <span className="text-text-body font-medium">
              {isDummy ? "Demo activity" : "Today's activity"}
            </span>
            <span className="mx-2 text-bg-divider">•</span>
            <span className="text-mono">{dateLabel}</span>
            {coldStartCount > 0 && !isDummy && (
              <>
                <span className="mx-2 text-bg-divider">•</span>
                <span className="text-mono text-accent-tealBright">
                  {coldStartCount} cold-start
                </span>
              </>
            )}
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <ColorLegend />
          <ViewToggle value={viewMode} onChange={setViewMode} />
        </div>
      </div>

      {/* Globe */}
      <div className="relative">
        <GlobeWrapper
          viewMode={viewMode}
          countryActivity={countryActivity}
          coordinationArcs={coordinationArcs}
        />
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
              {coldStartCount > 0 && !isDummy ? "by article count" : "by z-score"}
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
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span>
            Atlas Peak Media, LLC · {countryActivity.length} countries with data
            · US/FVEY excluded
          </span>
          <span className="text-mono">
            {isDummy ? "DEMO DATA" : "LIVE DATA"} ·{" "}
            {new Date().toLocaleTimeString("en-US", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </div>
      </footer>
    </main>
  );
}
