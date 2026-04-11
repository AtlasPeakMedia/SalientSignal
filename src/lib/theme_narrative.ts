/**
 * Theme narrative generator — Session 31 SCAME dashboard V1.5.
 *
 * Takes a list of CountryThemeRow for one (country, audience, period)
 * bucket and produces a natural-language summary paragraph that "reads
 * out all of the items that would be seen in SCAME" (Don's exact
 * request). This is the narrative companion to the word-cloud pill grid
 * rendered by CountryThemePanel.
 *
 * Zero LLM dependency — this is a pure template-based generator. The
 * LLM-authored version (Claude Haiku against the same theme lists) is
 * future work that needs an Anthropic API key; the template version gets
 * us 80% of the value for 0% of the cost and works today, offline.
 *
 * Design decisions:
 *   - Each sentence is built from a fixed template with the top theme
 *     labels interpolated. No free-form generation, no hallucination
 *     risk.
 *   - Tone interpretation uses the V1.5 avgTone scale (-10..+10). We
 *     bucket into "hostile" (<-4), "negative" (-4..-1), "neutral"
 *     (-1..+1), "positive" (+1..+4), "celebratory" (>+4).
 *   - Concentration uses the top theme's share: "dominated" (>25%),
 *     "led" (15-25%), "anchored around" (5-15%), "scattered across"
 *     (<5%).
 *   - The paragraph is intentionally brief (2-3 sentences) to stay
 *     scannable next to the word-cloud panel. A longer "deep dive"
 *     paragraph is V2 work.
 *
 * Usage (server component):
 *
 *   import { buildThemeNarrative } from "@/lib/theme_narrative";
 *
 *   const themes = await getCountryThemes("IR", "monthly");
 *   const domesticThemes = themes.filter(
 *     (t) => t.audienceType === "DOMESTIC" && t.periodStart === "2026-04-01"
 *   );
 *   const narrative = buildThemeNarrative({
 *     country: "Iran",
 *     audienceType: "DOMESTIC",
 *     period: "April 2026",
 *     themes: domesticThemes,
 *   });
 *   // → "In April 2026, Iran's state media targeting domestic audiences
 *   //    led with themes around Armed Conflict, Military, and Leaders
 *   //    (top three accounted for 38% of coverage). Average tone on
 *   //    those themes was negative, framing coverage around conflict
 *   //    and crisis. The broader month's coverage drew on an additional
 *   //    22 themes including Ethnicity, Religion, and Public Safety."
 */

import type { AudienceType, CountryThemeRow } from "./types";

export interface NarrativeInput {
  /** Display name of the country (e.g. "Iran", not "IR"). */
  country: string;
  /** Intended audience for this narrative. */
  audienceType: AudienceType;
  /** Human-readable period label (e.g. "April 2026" or "Week of April 6, 2026"). */
  period: string;
  /** Theme rows for this exact (country, audience, period) bucket. */
  themes: CountryThemeRow[];
}

type ToneBucket =
  | "hostile"
  | "negative"
  | "neutral"
  | "positive"
  | "celebratory"
  | "mixed"
  | "unknown";

interface ConcentrationBucket {
  verb: string;
  shareDescription: string;
}

function classifyTone(avgTone: number | null): ToneBucket {
  if (avgTone === null) return "unknown";
  if (avgTone < -4) return "hostile";
  if (avgTone < -1) return "negative";
  if (avgTone <= 1) return "neutral";
  if (avgTone <= 4) return "positive";
  return "celebratory";
}

function avgToneAcrossThemes(themes: CountryThemeRow[]): number | null {
  const tones = themes
    .map((t) => t.avgTone)
    .filter((t): t is number => t !== null);
  if (tones.length === 0) return null;
  return tones.reduce((a, b) => a + b, 0) / tones.length;
}

function describeConcentration(topShareSum: number): ConcentrationBucket {
  // topShareSum = sum of share for the top 3 themes
  if (topShareSum > 0.45) {
    return {
      verb: "was dominated by",
      shareDescription: `the top three themes accounted for ${Math.round(topShareSum * 100)}% of coverage`,
    };
  }
  if (topShareSum > 0.3) {
    return {
      verb: "led with",
      shareDescription: `the top three together made up ${Math.round(topShareSum * 100)}% of coverage`,
    };
  }
  if (topShareSum > 0.15) {
    return {
      verb: "anchored around",
      shareDescription: `the top three represented ${Math.round(topShareSum * 100)}% of coverage`,
    };
  }
  return {
    verb: "scattered across",
    shareDescription: `no single topic dominated — the top three combined for only ${Math.round(topShareSum * 100)}%`,
  };
}

function audiencePhrase(audience: AudienceType): string {
  switch (audience) {
    case "DOMESTIC":
      return "state media targeting domestic audiences";
    case "INTERNATIONAL":
      return "state media's international output (English and other non-native languages)";
    case "DIASPORA":
      return "state media aimed at diaspora communities abroad";
  }
}

function toneSentence(
  audience: AudienceType,
  tone: ToneBucket,
  country: string,
): string {
  switch (tone) {
    case "hostile":
      return `Average tone across those themes was sharply hostile, framing coverage around crisis, conflict, and external threats.`;
    case "negative":
      return `Average tone leaned negative, consistent with crisis- and conflict-framing typical of ${
        audience === "INTERNATIONAL"
          ? "outward-facing grievance narratives"
          : "domestic security messaging"
      }.`;
    case "neutral":
      return `Average tone was broadly neutral — coverage was descriptive rather than explicitly slanted.`;
    case "positive":
      return `Average tone was moderately positive, consistent with ${
        audience === "INTERNATIONAL"
          ? "soft-power and achievement narratives aimed at foreign audiences"
          : "domestic legitimacy and achievement narratives"
      }.`;
    case "celebratory":
      return `Average tone was strongly celebratory, typical of state-media messaging around commemoration, achievement, or leadership praise.`;
    case "mixed":
      return `Average tone was mixed — different themes carried markedly different framings.`;
    default:
      return `Tone data was unavailable for this period.`;
  }
}

function joinList(items: string[]): string {
  if (items.length === 0) return "";
  if (items.length === 1) return items[0];
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}

export function buildThemeNarrative(input: NarrativeInput): string {
  const { country, audienceType, period, themes } = input;

  if (themes.length === 0) {
    return `No ${audienceType.toLowerCase()} theme data was captured for ${country} during ${period}.`;
  }

  // Sort defensively — the aggregator should already return sorted, but
  // never trust upstream ordering for a presentation layer.
  const sorted = [...themes].sort((a, b) => b.articleCount - a.articleCount);

  const topThree = sorted.slice(0, 3);
  const topShareSum = topThree.reduce((acc, t) => acc + t.share, 0);
  const concentration = describeConcentration(topShareSum);

  const topLabels = topThree.map((t) => t.label);
  const topList = joinList(topLabels);

  const avgTone = avgToneAcrossThemes(topThree);
  const toneBucket = classifyTone(avgTone);

  const restCount = Math.max(0, sorted.length - 3);
  const restSampleLabels = sorted
    .slice(3, 6)
    .map((t) => t.label);
  const restSampleList = joinList(restSampleLabels);

  // Sentence 1 — lead
  const sentence1 = `In ${period}, ${country}'s ${audiencePhrase(
    audienceType,
  )} ${concentration.verb} ${topList} (${concentration.shareDescription}).`;

  // Sentence 2 — tone
  const sentence2 = toneSentence(audienceType, toneBucket, country);

  // Sentence 3 — long tail (only if there's meaningful tail)
  let sentence3 = "";
  if (restCount > 0) {
    if (restSampleLabels.length > 0) {
      sentence3 = ` The broader month's coverage drew on an additional ${restCount} theme${
        restCount === 1 ? "" : "s"
      } including ${restSampleList}.`;
    } else {
      sentence3 = ` The broader month's coverage drew on ${restCount} additional theme${
        restCount === 1 ? "" : "s"
      }.`;
    }
  }

  return `${sentence1} ${sentence2}${sentence3}`.trim();
}
