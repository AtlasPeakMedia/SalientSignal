"use client";

import { useState } from "react";
import type { DeviationLevel } from "@/lib/types";
import { DEVIATION_COLORS, DEVIATION_LABELS } from "@/lib/colors";

const ORDER: Array<DeviationLevel> = [
  "deepBlue",
  "steelBlue",
  "coolGray",
  "neutral",
  "amber",
  "orange",
  "red",
];

/**
 * Longer-form hover descriptions for the color legend. These explain WHAT
 * each level means analytically, beyond just the short one-word label.
 * Matches the methodology page's level mapping section.
 */
const LEVEL_TOOLTIPS: Record<DeviationLevel, string> = {
  deepBlue:
    "Significant silence. Output is under 30% of baseline AND z-score below -2. Often a signal that state media is actively avoiding a topic.",
  steelBlue:
    "Unusually quiet. Output under 50% of baseline with z-score below -1.5. Worth watching — not noise.",
  coolGray:
    "Slightly below normal. Ratio under 0.75 but z-score not extreme. Might just be a slow day.",
  neutral:
    "Normal range. Ratio 0.75 - 1.5 with no significant z-score. Baseline behavior.",
  amber:
    "Elevated. Ratio up to 2.5x AND z-score above 1.5. Moderate surge worth noting.",
  orange:
    "Significant spike. Ratio up to 4x AND z-score above 2. State media is meaningfully pushing something.",
  red: "Anomalous surge. Z-score 2.5 or higher regardless of ratio. A real anomaly — not noise.",
};

export default function ColorLegend() {
  const [hovered, setHovered] = useState<DeviationLevel | null>(null);

  return (
    <div className="relative inline-flex items-center gap-3 text-xs text-text-secondary">
      <span className="text-mono uppercase tracking-wider">Quiet</span>
      <div className="flex" role="img" aria-label="Deviation color scale">
        {ORDER.map((level) => (
          <button
            key={level}
            type="button"
            onMouseEnter={() => setHovered(level)}
            onMouseLeave={() => setHovered(null)}
            onFocus={() => setHovered(level)}
            onBlur={() => setHovered(null)}
            aria-label={`${DEVIATION_LABELS[level]}: ${LEVEL_TOOLTIPS[level]}`}
            className="w-6 h-3 first:rounded-l-sm last:rounded-r-sm hover:scale-y-150 focus:scale-y-150 transition-transform outline-none"
            style={{ backgroundColor: DEVIATION_COLORS[level] }}
          />
        ))}
      </div>
      <span className="text-mono uppercase tracking-wider">Surge</span>

      {hovered && (
        <div
          role="tooltip"
          className="absolute top-full right-0 mt-3 w-72 p-3 rounded-md border border-bg-divider bg-bg-card shadow-lg z-30 pointer-events-none"
        >
          <div className="flex items-center gap-2 mb-1.5">
            <span
              className="inline-block w-3 h-3 rounded-sm"
              style={{ backgroundColor: DEVIATION_COLORS[hovered] }}
            />
            <span className="text-sm font-semibold text-text-body">
              {DEVIATION_LABELS[hovered]}
            </span>
          </div>
          <p className="text-xs text-text-secondary leading-relaxed">
            {LEVEL_TOOLTIPS[hovered]}
          </p>
        </div>
      )}
    </div>
  );
}
