"use client";

import { useState } from "react";
import Link from "next/link";
import Wordmark from "@/components/Brand/Wordmark";
import ViewToggle from "@/components/Globe/ViewToggle";
import ColorLegend from "@/components/Globe/ColorLegend";
import GlobeWrapper from "@/components/Globe/GlobeWrapper";
import { TRENDING_THEMES, COUNTRY_ACTIVITY } from "@/lib/dummy-data";

type ViewMode = "DOMESTIC" | "INTERNATIONAL" | "BOTH";

export default function HomePage() {
  const [viewMode, setViewMode] = useState<ViewMode>("BOTH");

  // Top 5 most-elevated countries
  const topMovers = [...COUNTRY_ACTIVITY]
    .sort((a, b) => {
      const aMax = Math.max(a.domestic.zScore, a.international.zScore);
      const bMax = Math.max(b.domestic.zScore, b.international.zScore);
      return bMax - aMax;
    })
    .slice(0, 5);

  return (
    <main className="min-h-screen">
      {/* Header */}
      <header className="border-b border-bg-divider">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
          <Wordmark />
          <nav className="flex items-center gap-6 text-sm text-text-secondary">
            <Link href="/methodology" className="hover:text-text-body transition-colors">
              Methodology
            </Link>
            <Link href="/about" className="hover:text-text-body transition-colors">
              About
            </Link>
            <span className="text-mono text-xs px-2 py-1 rounded border border-bg-divider">
              DEMO
            </span>
          </nav>
        </div>
      </header>

      {/* Globe controls */}
      <div className="max-w-[1400px] mx-auto px-6 pt-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <h1 className="text-sm text-text-secondary">
            <span className="text-text-body font-medium">Today's activity</span>
            <span className="mx-2 text-bg-divider">•</span>
            <span className="text-mono">{new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}</span>
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <ColorLegend />
          <ViewToggle value={viewMode} onChange={setViewMode} />
        </div>
      </div>

      {/* Globe */}
      <div className="relative">
        <GlobeWrapper viewMode={viewMode} />
      </div>

      {/* Bottom panel — top movers + themes */}
      <section className="max-w-[1400px] mx-auto px-6 py-8 grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Top movers */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-text-body uppercase tracking-wider">
              Biggest Movers Today
            </h2>
            <span className="text-xs text-text-secondary text-mono">
              by z-score
            </span>
          </div>
          <ul className="space-y-3">
            {topMovers.map((country) => {
              const moreNotable =
                Math.abs(country.domestic.zScore) > Math.abs(country.international.zScore)
                  ? country.domestic
                  : country.international;
              const audience =
                Math.abs(country.domestic.zScore) > Math.abs(country.international.zScore)
                  ? "DOMESTIC"
                  : "INTERNATIONAL";
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
                          {audience.toLowerCase()} • z-score {moreNotable.zScore}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-mono text-sm text-amber-400">
                        {moreNotable.ratio}x
                      </div>
                      <div className="text-xs text-text-secondary">
                        {moreNotable.today} / {moreNotable.baseline}
                      </div>
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
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
          <ul className="space-y-2">
            {TRENDING_THEMES.map((theme) => {
              const isUp = theme.change.startsWith("+");
              return (
                <li
                  key={theme.theme}
                  className="flex items-center justify-between p-2.5 rounded-md hover:bg-bg-base/50 transition-colors"
                >
                  <span className="text-sm text-text-body">{theme.label}</span>
                  <div className="flex items-center gap-3 text-mono text-xs">
                    <span className="text-text-secondary">{theme.count}</span>
                    <span
                      className={
                        isUp ? "text-accent-tealBright" : "text-text-secondary"
                      }
                    >
                      {theme.change}
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      </section>

      {/* Footer */}
      <footer className="max-w-[1400px] mx-auto px-6 py-6 text-xs text-text-secondary border-t border-bg-divider">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span>
            Atlas Peak Media, LLC · {COUNTRY_ACTIVITY.length} countries monitored ·
            US/FVEY excluded
          </span>
          <span className="text-mono">
            Last update: {new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })} (DEMO DATA)
          </span>
        </div>
      </footer>
    </main>
  );
}
