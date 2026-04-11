/**
 * ThemeTimelineSparkline — inline mini-chart for one (audience, theme) trend
 * across the 15-month history.
 *
 * Session 31 V1.5 follow-up. Motivates the historical dataset by showing
 * HOW themes trend, not just their current volume. Example use case:
 * "How has Russia's DOMESTIC coverage of CEASEFIRE evolved since Jan 2025?"
 * Each month becomes a vertical bar, the height is article_count, hovering
 * shows the exact value + avgTone for that bucket.
 *
 * Rendered inside CountryThemePanel when the user clicks a theme pill
 * (V2 drill-down) — for V1 the panel just renders the word cloud, and
 * this component is standalone so it can be wired into drill-down flows
 * later without further changes.
 *
 * Design decisions:
 *   - Pure SVG. No chart library. 800 bytes of component code vs 150 KB
 *     of a recharts import. We only need a simple bar chart.
 *   - Responsive: the SVG scales to its container's width via viewBox.
 *   - Color: bars inherit the pill's tone class — red for hostile themes,
 *     amber for negative, neutral gray for flat, teal for positive.
 *   - Empty months (no article_count, not even zero) render as a thin
 *     dashed baseline so users see the gap. Full-zero months render as
 *     a thin solid line at zero to distinguish "we looked and there were
 *     zero" from "no data collected".
 *   - Accessibility: aria-label on each bar with the month + count + tone.
 */
"use client";

import type { CountryThemeRow } from "@/lib/types";

interface Props {
  /** All CountryThemeRow for a single (country, audience) — filtered by the
   *  parent to only include rows mentioning one specific theme. */
  rows: CountryThemeRow[];
  /** The theme code this sparkline is visualizing (for the aria-label). */
  theme: string;
  /** Height in pixels. The SVG width is responsive via viewBox. Default 40. */
  height?: number;
}

function formatPeriodShort(periodStart: string): string {
  try {
    const d = new Date(`${periodStart}T00:00:00Z`);
    return d.toLocaleDateString("en-US", {
      month: "short",
      year: "2-digit",
      timeZone: "UTC",
    });
  } catch {
    return periodStart;
  }
}

function toneBarColor(avgTone: number | null): string {
  if (avgTone === null) return "var(--color-text-secondary, #6b7280)";
  if (avgTone < -3) return "var(--color-accent-red, #D93025)";
  if (avgTone < -1) return "var(--color-accent-amber, #F5A623)";
  if (avgTone <= 1) return "var(--color-text-body, #9ca3af)";
  if (avgTone <= 3) return "var(--color-accent-tealBright, #00BFA5)";
  return "var(--color-accent-tealBright, #00BFA5)";
}

export default function ThemeTimelineSparkline({
  rows,
  theme,
  height = 40,
}: Props) {
  if (rows.length === 0) {
    return (
      <div
        className="text-xs text-text-secondary italic"
        aria-label={`No timeline data for ${theme}`}
      >
        No timeline data
      </div>
    );
  }

  // Sort by period_start ascending (left-to-right in the chart)
  const sorted = [...rows].sort((a, b) =>
    a.periodStart < b.periodStart ? -1 : 1,
  );

  const maxCount = Math.max(...sorted.map((r) => r.articleCount), 1);

  // Layout: each bar gets a fixed-width slot + 1px gap. We use a 0..N-1
  // coordinate space and let SVG scale it to container width.
  const barCount = sorted.length;
  const slotWidth = 10;
  const barWidth = 6;
  const gap = (slotWidth - barWidth) / 2;
  const chartWidth = barCount * slotWidth;
  const chartHeight = height;
  const barMaxHeight = chartHeight - 4; // reserve 4px for baseline

  return (
    <svg
      role="img"
      aria-label={`Monthly article count for ${theme}`}
      viewBox={`0 0 ${chartWidth} ${chartHeight}`}
      preserveAspectRatio="none"
      className="w-full"
      style={{ height: `${height}px` }}
    >
      {/* Baseline */}
      <line
        x1={0}
        y1={chartHeight - 1}
        x2={chartWidth}
        y2={chartHeight - 1}
        stroke="currentColor"
        strokeWidth={0.5}
        opacity={0.3}
      />
      {sorted.map((row, i) => {
        const barHeight = (row.articleCount / maxCount) * barMaxHeight;
        const x = i * slotWidth + gap;
        const y = chartHeight - barHeight - 1;
        const tooltip = `${formatPeriodShort(row.periodStart)}: ${row.articleCount} articles${
          row.avgTone !== null ? ` (avg tone ${row.avgTone.toFixed(1)})` : ""
        }`;
        return (
          <rect
            key={row.periodStart}
            x={x}
            y={y}
            width={barWidth}
            height={Math.max(barHeight, 0.5)}
            fill={toneBarColor(row.avgTone)}
            opacity={0.85}
          >
            <title>{tooltip}</title>
          </rect>
        );
      })}
    </svg>
  );
}
