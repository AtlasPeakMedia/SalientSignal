/**
 * Maps deviation level to hex color for the globe and UI.
 * Mirrors Algorithm 2 from the spec.
 */

import type { DeviationLevel } from "./types";

export const DEVIATION_COLORS: Record<DeviationLevel, string> = {
  deepBlue: "#1A3A5C",   // Significant silence
  steelBlue: "#4A7FB5",  // Unusually quiet
  coolGray: "#2F3A50",   // Slightly below normal (slight lift from near-black)
  neutral: "#3F5070",    // Normal range — was nearly invisible against the ocean, now a muted slate that reads without being flashy
  amber: "#F5A623",      // Elevated
  orange: "#E8601C",     // Significant spike
  red: "#D93025",        // Anomalous surge
};

export const DEVIATION_LABELS: Record<DeviationLevel, string> = {
  deepBlue: "Significant silence",
  steelBlue: "Unusually quiet",
  coolGray: "Slightly below normal",
  neutral: "Normal",
  amber: "Elevated",
  orange: "Significant spike",
  red: "Anomalous surge",
};

export function getColorForLevel(level: DeviationLevel): string {
  return DEVIATION_COLORS[level];
}
