/**
 * DUMMY DATA fixture for development and preview deployments.
 *
 * Shape of every export here mirrors the types in `./types.ts`, which is the
 * canonical source of truth. The unified data layer (`./data.ts`) reads
 * either this fixture or live Supabase rows depending on the feature flag.
 *
 * Country activity for ~150 countries (US/FVEY hardcoded excluded).
 */

import type {
  AudienceType,
  CountryActivity,
  CoordinationArc,
  DeviationLevel,
  Headline,
  TrendingTheme,
} from "./types";

// Re-export for legacy callers that still import types from here.
export type { AudienceType, CountryActivity, CoordinationArc, DeviationLevel, Headline, TrendingTheme };

/**
 * Calculate deviation level from ratio + z-score.
 * Mirrors Algorithm 2 from the spec.
 */
function getLevel(ratio: number, zScore: number): DeviationLevel {
  if (ratio < 0.3 && zScore < -2.0) return "deepBlue";
  if (ratio < 0.5 && zScore < -1.5) return "steelBlue";
  if (ratio < 0.75) return "coolGray";
  if (ratio <= 1.5) return "neutral";
  if (ratio <= 2.5 && zScore >= 1.5) return "amber";
  if (ratio <= 4.0 && zScore >= 2.0) return "orange";
  if (zScore >= 2.5) return "red";
  return "neutral";
}

function makeActivity(
  baseline: number,
  ratio: number
): CountryActivity["domestic"] {
  const today = Math.round(baseline * ratio);
  // Approximate z-score from ratio (assuming std ~ baseline * 0.3)
  const std = baseline * 0.3;
  const zScore = std > 0 ? (today - baseline) / std : 0;
  return {
    today,
    baseline,
    ratio: Math.round(ratio * 100) / 100,
    zScore: Math.round(zScore * 10) / 10,
    level: getLevel(ratio, zScore),
  };
}

// Tier 1 — primary adversaries
const tier1: Array<[string, string, string, string, number, number, number, number]> = [
  // [iso2, name, flag, region, dom_baseline, dom_ratio, intl_baseline, intl_ratio]
  ["RU", "Russia", "🇷🇺", "Eurasia", 850, 1.05, 280, 2.4],   // Intl spike
  ["CN", "China", "🇨🇳", "East Asia", 1200, 1.15, 450, 1.8],  // Intl moderate spike
  ["IR", "Iran", "🇮🇷", "Middle East", 380, 2.3, 95, 3.1],    // Both spiking
  ["KP", "North Korea", "🇰🇵", "East Asia", 35, 0.4, 12, 0.2], // Silent
];

// Tier 2 — regional powers
const tier2: Array<[string, string, string, string, number, number, number, number]> = [
  ["TR", "Turkey", "🇹🇷", "Middle East", 320, 1.6, 110, 1.3],
  ["SA", "Saudi Arabia", "🇸🇦", "Middle East", 280, 1.1, 140, 0.9],
  ["AE", "United Arab Emirates", "🇦🇪", "Middle East", 150, 0.9, 220, 1.0],
  ["QA", "Qatar", "🇶🇦", "Middle East", 90, 1.2, 380, 1.4],
  ["EG", "Egypt", "🇪🇬", "MENA", 260, 1.0, 80, 0.8],
  ["IL", "Israel", "🇮🇱", "Middle East", 340, 1.3, 145, 1.5],
  ["IN", "India", "🇮🇳", "South Asia", 980, 1.2, 240, 1.1],
  ["PK", "Pakistan", "🇵🇰", "South Asia", 220, 0.9, 60, 0.7],
  ["VE", "Venezuela", "🇻🇪", "Latin America", 180, 2.6, 95, 3.4],  // Coordination with RU
  ["CU", "Cuba", "🇨🇺", "Latin America", 65, 1.8, 45, 2.1],
  ["NI", "Nicaragua", "🇳🇮", "Latin America", 40, 1.5, 18, 1.7],
  ["BY", "Belarus", "🇧🇾", "Eastern Europe", 95, 0.5, 28, 0.4], // Quiet
];

// Tier 3 — broad coverage
const tier3: Array<[string, string, string, string, number, number, number, number]> = [
  // East Asia & Pacific
  ["JP", "Japan", "🇯🇵", "East Asia", 420, 1.0, 110, 0.95],
  ["KR", "South Korea", "🇰🇷", "East Asia", 380, 1.05, 90, 1.1],
  ["TW", "Taiwan", "🇹🇼", "East Asia", 220, 1.2, 65, 1.4],
  ["MN", "Mongolia", "🇲🇳", "East Asia", 45, 1.0, 15, 1.0],
  ["VN", "Vietnam", "🇻🇳", "Southeast Asia", 180, 1.0, 55, 1.0],
  ["LA", "Laos", "🇱🇦", "Southeast Asia", 22, 0.9, 8, 0.8],
  ["KH", "Cambodia", "🇰🇭", "Southeast Asia", 35, 1.0, 12, 1.0],
  ["MM", "Myanmar", "🇲🇲", "Southeast Asia", 65, 1.4, 18, 1.6],
  ["TH", "Thailand", "🇹🇭", "Southeast Asia", 240, 1.0, 70, 0.95],
  ["PH", "Philippines", "🇵🇭", "Southeast Asia", 180, 1.0, 50, 1.0],
  ["MY", "Malaysia", "🇲🇾", "Southeast Asia", 145, 1.05, 45, 1.1],
  ["SG", "Singapore", "🇸🇬", "Southeast Asia", 95, 1.0, 220, 1.0],
  ["ID", "Indonesia", "🇮🇩", "Southeast Asia", 290, 1.1, 60, 1.0],

  // South Asia
  ["BD", "Bangladesh", "🇧🇩", "South Asia", 85, 1.0, 22, 1.0],
  ["LK", "Sri Lanka", "🇱🇰", "South Asia", 60, 1.0, 18, 1.0],
  ["NP", "Nepal", "🇳🇵", "South Asia", 35, 1.0, 10, 1.0],
  ["BT", "Bhutan", "🇧🇹", "South Asia", 12, 1.0, 4, 1.0],
  ["AF", "Afghanistan", "🇦🇫", "South Asia", 45, 0.6, 15, 0.5],

  // Central Asia
  ["KZ", "Kazakhstan", "🇰🇿", "Central Asia", 110, 1.0, 35, 1.0],
  ["UZ", "Uzbekistan", "🇺🇿", "Central Asia", 70, 1.0, 18, 1.0],
  ["TM", "Turkmenistan", "🇹🇲", "Central Asia", 18, 1.0, 5, 0.8],
  ["TJ", "Tajikistan", "🇹🇯", "Central Asia", 25, 1.0, 7, 1.0],
  ["KG", "Kyrgyzstan", "🇰🇬", "Central Asia", 30, 1.0, 8, 1.0],

  // MENA
  ["IQ", "Iraq", "🇮🇶", "Middle East", 95, 1.1, 28, 1.0],
  ["SY", "Syria", "🇸🇾", "Middle East", 75, 1.4, 22, 1.5],
  ["LB", "Lebanon", "🇱🇧", "Middle East", 60, 1.2, 25, 1.3],
  ["JO", "Jordan", "🇯🇴", "Middle East", 55, 1.0, 18, 1.0],
  ["BH", "Bahrain", "🇧🇭", "Middle East", 30, 1.0, 12, 1.0],
  ["KW", "Kuwait", "🇰🇼", "Middle East", 65, 1.0, 22, 1.0],
  ["OM", "Oman", "🇴🇲", "Middle East", 40, 1.0, 14, 1.0],
  ["YE", "Yemen", "🇾🇪", "Middle East", 35, 1.5, 12, 1.7],
  ["LY", "Libya", "🇱🇾", "MENA", 25, 1.1, 8, 1.0],
  ["TN", "Tunisia", "🇹🇳", "MENA", 50, 1.0, 16, 1.0],
  ["DZ", "Algeria", "🇩🇿", "MENA", 90, 1.0, 28, 1.0],
  ["MA", "Morocco", "🇲🇦", "MENA", 110, 1.0, 35, 1.0],
  ["PS", "Palestine", "🇵🇸", "Middle East", 45, 1.6, 18, 1.8],

  // Sub-Saharan Africa
  ["NG", "Nigeria", "🇳🇬", "West Africa", 180, 1.0, 45, 1.0],
  ["ZA", "South Africa", "🇿🇦", "Southern Africa", 220, 1.0, 60, 1.0],
  ["KE", "Kenya", "🇰🇪", "East Africa", 130, 1.0, 35, 1.0],
  ["ET", "Ethiopia", "🇪🇹", "East Africa", 95, 1.1, 25, 1.0],
  ["ER", "Eritrea", "🇪🇷", "East Africa", 12, 0.7, 4, 0.6],
  ["SO", "Somalia", "🇸🇴", "East Africa", 30, 1.2, 10, 1.1],
  ["SD", "Sudan", "🇸🇩", "East Africa", 55, 1.3, 18, 1.4],
  ["SS", "South Sudan", "🇸🇸", "East Africa", 18, 1.0, 6, 1.0],
  ["CD", "DR Congo", "🇨🇩", "Central Africa", 80, 1.0, 22, 1.0],
  ["CG", "Congo", "🇨🇬", "Central Africa", 25, 1.0, 8, 1.0],
  ["RW", "Rwanda", "🇷🇼", "East Africa", 40, 1.0, 14, 1.0],
  ["UG", "Uganda", "🇺🇬", "East Africa", 60, 1.0, 18, 1.0],
  ["TZ", "Tanzania", "🇹🇿", "East Africa", 70, 1.0, 20, 1.0],
  ["MZ", "Mozambique", "🇲🇿", "Southern Africa", 35, 1.0, 12, 1.0],
  ["AO", "Angola", "🇦🇴", "Central Africa", 50, 1.0, 16, 1.0],
  ["ZW", "Zimbabwe", "🇿🇼", "Southern Africa", 45, 1.0, 14, 1.0],
  ["ZM", "Zambia", "🇿🇲", "Southern Africa", 35, 1.0, 12, 1.0],
  ["GH", "Ghana", "🇬🇭", "West Africa", 80, 1.0, 22, 1.0],
  ["SN", "Senegal", "🇸🇳", "West Africa", 50, 1.0, 16, 1.0],
  ["CI", "Ivory Coast", "🇨🇮", "West Africa", 60, 1.0, 18, 1.0],
  ["ML", "Mali", "🇲🇱", "West Africa", 35, 1.0, 12, 1.0],
  ["BF", "Burkina Faso", "🇧🇫", "West Africa", 30, 1.0, 10, 1.0],
  ["NE", "Niger", "🇳🇪", "West Africa", 25, 1.0, 8, 1.0],
  ["TD", "Chad", "🇹🇩", "Central Africa", 20, 1.0, 7, 1.0],
  ["CM", "Cameroon", "🇨🇲", "Central Africa", 55, 1.0, 16, 1.0],

  // Europe (non-FVEY)
  ["UA", "Ukraine", "🇺🇦", "Eastern Europe", 380, 1.4, 120, 1.6],
  ["MD", "Moldova", "🇲🇩", "Eastern Europe", 45, 1.0, 14, 1.0],
  ["GE", "Georgia", "🇬🇪", "Caucasus", 60, 1.0, 18, 1.0],
  ["AM", "Armenia", "🇦🇲", "Caucasus", 50, 1.0, 16, 1.0],
  ["AZ", "Azerbaijan", "🇦🇿", "Caucasus", 70, 1.0, 22, 1.0],
  ["RS", "Serbia", "🇷🇸", "Balkans", 90, 1.0, 28, 1.0],
  ["BA", "Bosnia & Herzegovina", "🇧🇦", "Balkans", 50, 1.0, 16, 1.0],
  ["ME", "Montenegro", "🇲🇪", "Balkans", 25, 1.0, 8, 1.0],
  ["MK", "North Macedonia", "🇲🇰", "Balkans", 30, 1.0, 10, 1.0],
  ["XK", "Kosovo", "🇽🇰", "Balkans", 22, 1.0, 8, 1.0],
  ["AL", "Albania", "🇦🇱", "Balkans", 40, 1.0, 12, 1.0],
  ["HR", "Croatia", "🇭🇷", "Balkans", 70, 1.0, 22, 1.0],
  ["SI", "Slovenia", "🇸🇮", "Central Europe", 60, 1.0, 18, 1.0],
  ["HU", "Hungary", "🇭🇺", "Central Europe", 110, 1.05, 35, 1.0],
  ["PL", "Poland", "🇵🇱", "Central Europe", 160, 1.0, 45, 1.0],
  ["CZ", "Czech Republic", "🇨🇿", "Central Europe", 130, 1.0, 38, 1.0],
  ["SK", "Slovakia", "🇸🇰", "Central Europe", 70, 1.0, 22, 1.0],
  ["RO", "Romania", "🇷🇴", "Eastern Europe", 120, 1.0, 35, 1.0],
  ["BG", "Bulgaria", "🇧🇬", "Eastern Europe", 80, 1.0, 25, 1.0],
  ["GR", "Greece", "🇬🇷", "Southern Europe", 110, 1.0, 35, 1.0],
  ["IT", "Italy", "🇮🇹", "Southern Europe", 240, 1.0, 70, 1.0],
  ["ES", "Spain", "🇪🇸", "Southern Europe", 220, 1.0, 65, 1.0],
  ["PT", "Portugal", "🇵🇹", "Southern Europe", 95, 1.0, 28, 1.0],
  ["FR", "France", "🇫🇷", "Western Europe", 280, 1.0, 95, 1.05],
  ["DE", "Germany", "🇩🇪", "Western Europe", 320, 1.0, 110, 1.0],
  ["NL", "Netherlands", "🇳🇱", "Western Europe", 140, 1.0, 40, 1.0],
  ["BE", "Belgium", "🇧🇪", "Western Europe", 95, 1.0, 28, 1.0],
  ["CH", "Switzerland", "🇨🇭", "Western Europe", 85, 1.0, 25, 1.0],
  ["AT", "Austria", "🇦🇹", "Central Europe", 90, 1.0, 28, 1.0],
  ["DK", "Denmark", "🇩🇰", "Northern Europe", 80, 1.0, 22, 1.0],
  ["NO", "Norway", "🇳🇴", "Northern Europe", 75, 1.0, 22, 1.0],
  ["SE", "Sweden", "🇸🇪", "Northern Europe", 95, 1.0, 28, 1.0],
  ["FI", "Finland", "🇫🇮", "Northern Europe", 70, 1.0, 20, 1.0],
  ["IS", "Iceland", "🇮🇸", "Northern Europe", 22, 1.0, 6, 1.0],
  ["EE", "Estonia", "🇪🇪", "Baltic", 35, 1.0, 10, 1.0],
  ["LV", "Latvia", "🇱🇻", "Baltic", 35, 1.0, 10, 1.0],
  ["LT", "Lithuania", "🇱🇹", "Baltic", 40, 1.0, 12, 1.0],
  ["MT", "Malta", "🇲🇹", "Southern Europe", 18, 1.0, 5, 1.0],

  // Latin America & Caribbean
  ["MX", "Mexico", "🇲🇽", "North America", 210, 1.0, 55, 1.0],
  ["GT", "Guatemala", "🇬🇹", "Central America", 50, 1.0, 14, 1.0],
  ["HN", "Honduras", "🇭🇳", "Central America", 35, 1.0, 10, 1.0],
  ["SV", "El Salvador", "🇸🇻", "Central America", 40, 1.0, 12, 1.0],
  ["CR", "Costa Rica", "🇨🇷", "Central America", 30, 1.0, 9, 1.0],
  ["PA", "Panama", "🇵🇦", "Central America", 35, 1.0, 12, 1.0],
  ["CO", "Colombia", "🇨🇴", "South America", 160, 1.0, 45, 1.0],
  ["EC", "Ecuador", "🇪🇨", "South America", 65, 1.0, 18, 1.0],
  ["PE", "Peru", "🇵🇪", "South America", 110, 1.0, 30, 1.0],
  ["BO", "Bolivia", "🇧🇴", "South America", 55, 1.0, 16, 1.0],
  ["BR", "Brazil", "🇧🇷", "South America", 320, 1.0, 95, 1.0],
  ["PY", "Paraguay", "🇵🇾", "South America", 30, 1.0, 9, 1.0],
  ["UY", "Uruguay", "🇺🇾", "South America", 40, 1.0, 12, 1.0],
  ["AR", "Argentina", "🇦🇷", "South America", 180, 1.0, 50, 1.0],
  ["CL", "Chile", "🇨🇱", "South America", 130, 1.0, 38, 1.0],
  ["DO", "Dominican Republic", "🇩🇴", "Caribbean", 45, 1.0, 14, 1.0],
  ["HT", "Haiti", "🇭🇹", "Caribbean", 22, 1.0, 8, 1.0],
];

const allRows = [...tier1, ...tier2, ...tier3];

// Stable fixture date used by the dummy data path. MUST be stable (not new Date())
// to avoid SSR/client hydration mismatches in Firefox — see B7 in the plan file.
const DUMMY_FIXTURE_DATE = "2026-04-10";

export const COUNTRY_ACTIVITY: CountryActivity[] = allRows.map(
  ([iso2, name, flag, region, domBaseline, domRatio, intlBaseline, intlRatio]) => ({
    iso2,
    name,
    flag,
    region,
    domestic: makeActivity(domBaseline, domRatio),
    international: makeActivity(intlBaseline, intlRatio),
    latestDate: DUMMY_FIXTURE_DATE,
  })
);

/**
 * Get activity for a specific country.
 */
export function getCountryActivity(iso2: string): CountryActivity | null {
  return COUNTRY_ACTIVITY.find((c) => c.iso2 === iso2.toUpperCase()) ?? null;
}

/**
 * Coordination arcs — countries pushing the same theme within a 24-hour window.
 * Each arc connects two countries and represents detected coordination.
 * Interface lives in ./types.ts.
 */
export const COORDINATION_ARCS: CoordinationArc[] = [
  // Iran-coordinated regional narratives
  {
    startIso: "RU",
    endIso: "VE",
    theme: "ECONOMIC_COERCION",
    themeLabel: "Economic Coercion",
    countries: ["RU", "VE", "CU"],
    score: 0.78,
    startCountry: "Russia",
    endCountry: "Venezuela",
  },
  {
    startIso: "RU",
    endIso: "CU",
    theme: "ECONOMIC_COERCION",
    themeLabel: "Economic Coercion",
    countries: ["RU", "VE", "CU"],
    score: 0.78,
    startCountry: "Russia",
    endCountry: "Cuba",
  },
  {
    startIso: "VE",
    endIso: "CU",
    theme: "ECONOMIC_COERCION",
    themeLabel: "Economic Coercion",
    countries: ["RU", "VE", "CU"],
    score: 0.78,
    startCountry: "Venezuela",
    endCountry: "Cuba",
  },
  // Iran-Syria axis
  {
    startIso: "IR",
    endIso: "SY",
    theme: "WESTERN_HYPOCRISY",
    themeLabel: "Western Hypocrisy",
    countries: ["IR", "SY", "YE"],
    score: 0.65,
    startCountry: "Iran",
    endCountry: "Syria",
  },
  {
    startIso: "IR",
    endIso: "YE",
    theme: "WESTERN_HYPOCRISY",
    themeLabel: "Western Hypocrisy",
    countries: ["IR", "SY", "YE"],
    score: 0.65,
    startCountry: "Iran",
    endCountry: "Yemen",
  },
];

/**
 * Dummy headlines for showcase countries. Interface lives in ./types.ts.
 */
export const HEADLINES: Record<string, Headline[]> = {
  RU: [
    {
      outlet: "RT",
      outletLanguage: "es",
      audienceType: "INTERNATIONAL",
      title:
        "Cumbre de Europa Oriental impone condiciones económicas a países en desarrollo, denuncian analistas",
      publishedAt: "2026-04-09T14:30:00Z",
      url: "https://actualidad.rt.com/",
      themes: ["ECONOMIC_COERCION", "WESTERN_HYPOCRISY"],
    },
    {
      outlet: "RT",
      outletLanguage: "en",
      audienceType: "INTERNATIONAL",
      title:
        "Eastern European Summit Concludes With Renewed Security Concerns Over NATO Posture",
      publishedAt: "2026-04-09T14:25:00Z",
      url: "https://www.rt.com/",
      themes: ["NATO_AGGRESSION"],
    },
    {
      outlet: "RT",
      outletLanguage: "ar",
      audienceType: "INTERNATIONAL",
      title: "قمة أوروبا الشرقية: تأكيد جديد على مخاوف التهجير المدني والأمن الإقليمي",
      publishedAt: "2026-04-09T14:20:00Z",
      url: "https://arabic.rt.com/",
      themes: ["WESTERN_HYPOCRISY"],
    },
    {
      outlet: "TASS",
      outletLanguage: "ru",
      audienceType: "DOMESTIC",
      title: "Лавров: Россия продолжит защищать суверенитет в условиях санкционного давления",
      publishedAt: "2026-04-09T13:00:00Z",
      url: "https://tass.ru/",
      themes: ["SOVEREIGNTY", "ECONOMIC_COERCION"],
    },
    {
      outlet: "Sputnik",
      outletLanguage: "es",
      audienceType: "INTERNATIONAL",
      title:
        "Países latinoamericanos rechazan presiones occidentales en foro multilateral",
      publishedAt: "2026-04-09T12:45:00Z",
      url: "https://sputniknews.lat/",
      themes: ["MULTIPOLARITY"],
    },
    {
      outlet: "Rossiya 1",
      outletLanguage: "ru",
      audienceType: "DOMESTIC",
      title: "Президент провёл встречу с правительством по экономическим вопросам",
      publishedAt: "2026-04-09T11:30:00Z",
      url: "https://russia.tv/",
      themes: ["REGIME_LEGITIMACY"],
    },
    {
      outlet: "Vesti.ru",
      outletLanguage: "ru",
      audienceType: "DOMESTIC",
      title: "Минобороны: успешно проведены плановые учения войск",
      publishedAt: "2026-04-09T10:15:00Z",
      url: "https://www.vesti.ru/",
      themes: ["MILITARY_STRENGTH"],
    },
  ],
  CN: [
    {
      outlet: "CGTN",
      outletLanguage: "en",
      audienceType: "INTERNATIONAL",
      title: "Belt and Road Partners Mark Growing Trade Volumes Despite Western Pressure",
      publishedAt: "2026-04-09T15:00:00Z",
      url: "https://www.cgtn.com/",
      themes: ["DEVELOPMENT_MODEL", "MULTIPOLARITY"],
    },
    {
      outlet: "Xinhua",
      outletLanguage: "en",
      audienceType: "INTERNATIONAL",
      title: "China Calls for Multilateral Approach to Regional Security in ASEAN Forum",
      publishedAt: "2026-04-09T14:30:00Z",
      url: "https://english.news.cn/",
      themes: ["MULTIPOLARITY", "SOVEREIGNTY"],
    },
    {
      outlet: "Global Times",
      outletLanguage: "en",
      audienceType: "INTERNATIONAL",
      title: "US Military Exercises Near Taiwan Strait Risk Regional Stability, Experts Warn",
      publishedAt: "2026-04-09T13:00:00Z",
      url: "https://www.globaltimes.cn/",
      themes: ["TAIWAN_SOVEREIGNTY", "NATO_AGGRESSION"],
    },
    {
      outlet: "CCTV",
      outletLanguage: "zh",
      audienceType: "DOMESTIC",
      title: "国务院召开会议研究部署经济工作",
      publishedAt: "2026-04-09T12:00:00Z",
      url: "https://www.cctv.com/",
      themes: ["REGIME_LEGITIMACY"],
    },
    {
      outlet: "People's Daily",
      outletLanguage: "zh",
      audienceType: "DOMESTIC",
      title: "新时代中国特色社会主义思想引领高质量发展",
      publishedAt: "2026-04-09T11:00:00Z",
      url: "http://www.people.com.cn/",
      themes: ["REGIME_LEGITIMACY"],
    },
    {
      outlet: "CGTN Español",
      outletLanguage: "es",
      audienceType: "INTERNATIONAL",
      title: "China impulsa cooperación económica con países latinoamericanos",
      publishedAt: "2026-04-09T10:30:00Z",
      url: "https://espanol.cgtn.com/",
      themes: ["DEVELOPMENT_MODEL"],
    },
  ],
  IR: [
    {
      outlet: "Press TV",
      outletLanguage: "en",
      audienceType: "INTERNATIONAL",
      title:
        "Western Sanctions Regime Continues to Harm Civilian Populations, UN Rapporteur Reports",
      publishedAt: "2026-04-09T14:00:00Z",
      url: "https://www.presstv.ir/",
      themes: ["WESTERN_HYPOCRISY", "ECONOMIC_COERCION"],
    },
    {
      outlet: "IRNA",
      outletLanguage: "fa",
      audienceType: "DOMESTIC",
      title: "رئیس‌جمهور: ایران در برابر فشارهای اقتصادی مستحکم باقی می‌ماند",
      publishedAt: "2026-04-09T13:30:00Z",
      url: "https://www.irna.ir/",
      themes: ["SOVEREIGNTY", "REGIME_LEGITIMACY"],
    },
    {
      outlet: "Fars News",
      outletLanguage: "fa",
      audienceType: "DOMESTIC",
      title: "نیروهای مسلح ایران رزمایش مشترک منطقه‌ای را با موفقیت برگزار کردند",
      publishedAt: "2026-04-09T12:00:00Z",
      url: "https://www.farsnews.ir/",
      themes: ["MILITARY_STRENGTH"],
    },
    {
      outlet: "Al Alam",
      outletLanguage: "ar",
      audienceType: "INTERNATIONAL",
      title: "إيران تدعو إلى تعاون إقليمي مستقل عن التدخلات الغربية",
      publishedAt: "2026-04-09T11:30:00Z",
      url: "https://www.alalam.ir/",
      themes: ["MULTIPOLARITY", "SOVEREIGNTY"],
    },
  ],
  VE: [
    {
      outlet: "TeleSUR",
      outletLanguage: "es",
      audienceType: "INTERNATIONAL",
      title: "Maduro denuncia bloqueo económico ilegal y llama a solidaridad regional",
      publishedAt: "2026-04-09T14:15:00Z",
      url: "https://www.telesurtv.net/",
      themes: ["ECONOMIC_COERCION", "WESTERN_HYPOCRISY"],
    },
    {
      outlet: "VTV",
      outletLanguage: "es",
      audienceType: "DOMESTIC",
      title: "Gobierno presenta plan de desarrollo económico para 2026",
      publishedAt: "2026-04-09T13:00:00Z",
      url: "https://www.vtv.gob.ve/",
      themes: ["REGIME_LEGITIMACY"],
    },
  ],
};

/**
 * Get headlines for a specific country.
 */
export function getCountryHeadlines(iso2: string): Headline[] {
  return HEADLINES[iso2.toUpperCase()] ?? [];
}

/**
 * Top trending themes today across all monitored countries.
 */
export const TRENDING_THEMES = [
  { theme: "WESTERN_HYPOCRISY", label: "Western Hypocrisy", count: 247, change: "+34%" },
  { theme: "ECONOMIC_COERCION", label: "Economic Coercion", count: 198, change: "+62%" },
  { theme: "NATO_AGGRESSION", label: "NATO Aggression", count: 156, change: "+12%" },
  { theme: "TAIWAN_SOVEREIGNTY", label: "Taiwan Sovereignty", count: 134, change: "+8%" },
  { theme: "MULTIPOLARITY", label: "Multipolarity", count: 121, change: "+25%" },
  { theme: "SOVEREIGNTY", label: "Sovereignty", count: 109, change: "+5%" },
  { theme: "DEVELOPMENT_MODEL", label: "Development Partnership", count: 87, change: "+15%" },
  { theme: "MILITARY_STRENGTH", label: "Military Strength", count: 78, change: "−3%" },
];
