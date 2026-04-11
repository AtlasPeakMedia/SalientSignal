/**
 * Tests for buildThemeNarrative (Session 31 SCAME dashboard V1.5).
 *
 * Pure-function tests, no React, no data layer. Run with:
 *   npx vitest run src/lib/theme_narrative.test.ts
 *
 * (Project doesn't have vitest yet — this file stays as documentation
 * of expected behavior. Can be promoted to a real runner when the
 * frontend grows a test suite. For now the tests serve as an executable
 * spec / smoke check via `npx tsx src/lib/theme_narrative.test.ts`
 * once tsx is added, or just reading the assertions to understand the
 * narrative output shape.)
 */

import { buildThemeNarrative, type NarrativeInput } from "./theme_narrative";
import type { CountryThemeRow } from "./types";

function makeTheme(
  theme: string,
  articleCount: number,
  bucketTotal: number,
  avgTone: number | null = 0,
): CountryThemeRow {
  return {
    country: "IR",
    audienceType: "INTERNATIONAL",
    periodStart: "2026-04-01",
    periodEnd: "2026-04-30",
    theme,
    label: theme
      .replace(/_/g, " ")
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase()),
    articleCount,
    bucketTotal,
    share: articleCount / bucketTotal,
    avgTone,
  };
}

const SCENARIOS: Array<{
  name: string;
  input: NarrativeInput;
  mustContain: string[];
}> = [
  {
    name: "hostile Iran INTL (Israel conflict period)",
    input: {
      country: "Iran",
      audienceType: "INTERNATIONAL",
      period: "April 2026",
      themes: [
        makeTheme("ARMEDCONFLICT", 15, 50, -7.2),
        makeTheme("CEASEFIRE", 12, 50, -6.8),
        makeTheme("TAX_RELIGION_ISLAMIC", 10, 50, -5.5),
        makeTheme("KILL", 8, 50, -7.9),
        makeTheme("NEGOTIATIONS", 7, 50, -5.1),
      ],
    },
    mustContain: [
      "Iran's state media's international output",
      "April 2026",
      "Armedconflict",
      "hostile",
    ],
  },
  {
    name: "celebratory CN DOM (Chinese New Year)",
    input: {
      country: "China",
      audienceType: "DOMESTIC",
      period: "February 2025",
      themes: [
        makeTheme("TAX_HOLIDAYS", 40, 100, 6.5),
        makeTheme("CELEBRATION", 30, 100, 7.2),
        makeTheme("ECONOMY", 15, 100, 4.0),
      ],
    },
    mustContain: [
      "China's state media targeting domestic audiences",
      "February 2025",
      "celebratory",
    ],
  },
  {
    name: "scattered TR DOM (normal news month)",
    input: {
      country: "Turkey",
      audienceType: "DOMESTIC",
      period: "March 2026",
      themes: [
        makeTheme("TAX_FNCACT", 8, 200, -1.5),
        makeTheme("EPU_POLICY", 6, 200, -1.2),
        makeTheme("LEADER", 5, 200, -0.8),
        ...Array.from({ length: 20 }, (_, i) =>
          makeTheme(`THEME_${i}`, 2, 200, -0.5),
        ),
      ],
    },
    mustContain: [
      "Turkey's state media targeting domestic audiences",
      "scattered across",
    ],
  },
  {
    name: "empty bucket returns a single-sentence placeholder",
    input: {
      country: "Syria",
      audienceType: "DOMESTIC",
      period: "January 2025",
      themes: [],
    },
    mustContain: ["No domestic theme data was captured for Syria"],
  },
];

// ---------------------------------------------------------------------------
// Minimal test runner — print results to stdout
// ---------------------------------------------------------------------------
let passed = 0;
let failed = 0;

for (const scenario of SCENARIOS) {
  const narrative = buildThemeNarrative(scenario.input);
  const missing = scenario.mustContain.filter((s) => !narrative.includes(s));
  if (missing.length === 0) {
    console.log(`PASS  ${scenario.name}`);
    console.log(`      → "${narrative}"`);
    passed++;
  } else {
    console.log(`FAIL  ${scenario.name}`);
    console.log(`      missing: ${JSON.stringify(missing)}`);
    console.log(`      got: "${narrative}"`);
    failed++;
  }
}

console.log();
console.log(`${passed} passed, ${failed} failed, ${SCENARIOS.length} total`);
if (failed > 0) {
  if (typeof process !== "undefined") {
    process.exit(1);
  }
  throw new Error(`${failed} narrative tests failed`);
}
