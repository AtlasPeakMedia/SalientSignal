"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { CountryActivity, CoordinationArc, DeviationLevel } from "@/lib/types";
import { getColorForLevel } from "@/lib/colors";

// Globe.gl is client-only — dynamic import disables SSR
const Globe = dynamic(() => import("react-globe.gl"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full text-text-secondary">
      Loading globe…
    </div>
  ),
});

type ViewMode = "DOMESTIC" | "INTERNATIONAL" | "BOTH";

interface GeoFeature {
  type: "Feature";
  properties: {
    ISO_A2?: string;
    ISO_A2_EH?: string;
    ADMIN?: string;
    NAME?: string;
    [key: string]: unknown;
  };
  geometry: {
    type: string;
    coordinates: unknown;
  };
}

/**
 * Natural Earth has -99 for some countries' ISO_A2 (Norway, France, Kosovo).
 * Fall back to ISO_A2_EH (extended) which has the correct codes.
 */
function getIsoCode(props: GeoFeature["properties"]): string | undefined {
  const a2 = props.ISO_A2;
  if (a2 && a2 !== "-99") return a2;
  const a2eh = props.ISO_A2_EH;
  if (a2eh && a2eh !== "-99") return a2eh;
  return undefined;
}

interface GeoJson {
  type: "FeatureCollection";
  features: GeoFeature[];
}

interface Props {
  viewMode: ViewMode;
  countryActivity: CountryActivity[];
  coordinationArcs: CoordinationArc[];
}

// Approximate country centroids used for arc endpoints. Natural Earth has
// centroid data but we don't need precision for this visualization — these
// hand-picked points look fine for the coordination lines.
const COUNTRY_CENTROIDS: Record<string, [number, number]> = {
  RU: [61.524, 105.3188],
  CN: [35.8617, 104.1954],
  IR: [32.4279, 53.688],
  KP: [40.3399, 127.5101],
  VE: [6.4238, -66.5897],
  CU: [21.5218, -77.7812],
  SY: [34.8021, 38.9968],
  YE: [15.5527, 48.5164],
  NI: [12.8654, -85.2072],
  BY: [53.7098, 27.9534],
  UA: [48.3794, 31.1656],
  TR: [38.9637, 35.2433],
  SA: [23.8859, 45.0792],
  AE: [23.4241, 53.8478],
  QA: [25.3548, 51.1839],
  EG: [26.8206, 30.8025],
  TW: [23.6978, 120.9605],
  KH: [12.5657, 104.991],
  DE: [51.1657, 10.4515],
  FR: [46.2276, 2.2137],
};

function getCountryColor(
  isoA2: string | undefined,
  viewMode: ViewMode,
  activityByIso: Map<string, CountryActivity>,
): string {
  // Fallbacks use getColorForLevel("neutral") so there's a single source
  // of truth — if the neutral deviation color changes in colors.ts, the
  // unmonitored country fill stays in sync automatically.
  if (!isoA2) return getColorForLevel("neutral");
  const activity = activityByIso.get(isoA2);
  if (!activity) return getColorForLevel("neutral"); // Unmonitored country = neutral

  let level: DeviationLevel;
  if (viewMode === "DOMESTIC") {
    level = activity.domestic.level;
  } else if (viewMode === "INTERNATIONAL") {
    level = activity.international.level;
  } else {
    // BOTH — use the more anomalous of the two (highest abs z-score)
    const domAbs = Math.abs(activity.domestic.zScore);
    const intlAbs = Math.abs(activity.international.zScore);
    level = domAbs > intlAbs ? activity.domestic.level : activity.international.level;
  }
  return getColorForLevel(level);
}

export default function GlobeWrapper({
  viewMode,
  countryActivity,
  coordinationArcs,
}: Props) {
  const router = useRouter();
  const globeRef = useRef<unknown>(null);
  const [geoData, setGeoData] = useState<GeoJson | null>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  // Track which country the cursor is currently over. Drives altitude lift,
  // fill color swap, and border glow on hover.
  const [hoveredIso, setHoveredIso] = useState<string | null>(null);

  // Respect prefers-reduced-motion for the polygon altitude animation.
  // react-globe.gl's THREE.js tweens don't auto-respect this OS-level
  // preference, so we manually gate polygonsTransitionDuration on it.
  const [reducedMotion, setReducedMotion] = useState(false);

  // Memoize the ISO lookup map so we don't rebuild it on every render.
  const activityByIso = useMemo(
    () => new Map<string, CountryActivity>(countryActivity.map((c) => [c.iso2, c])),
    [countryActivity],
  );

  useEffect(() => {
    fetch("/data/ne_110m_admin_0_countries.geojson")
      .then((r) => r.json())
      .then((data: GeoJson) => setGeoData(data))
      .catch(() => {
        console.warn("Country boundaries not loaded. Run scripts/fetch-geojson.sh");
      });
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  useEffect(() => {
    function updateSize() {
      const w = Math.min(window.innerWidth, 1400);
      const h = window.innerHeight - 180;
      setDimensions({ width: w, height: h });
    }
    updateSize();
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  // Build arc data with lat/lng coordinates, skipping any arc whose endpoints
  // we don't have centroids for.
  const arcData = useMemo(
    () =>
      coordinationArcs
        .filter(
          (arc) =>
            COUNTRY_CENTROIDS[arc.startIso] && COUNTRY_CENTROIDS[arc.endIso],
        )
        .map((arc) => {
          const [startLat, startLng] = COUNTRY_CENTROIDS[arc.startIso];
          const [endLat, endLng] = COUNTRY_CENTROIDS[arc.endIso];
          return {
            startLat,
            startLng,
            endLat,
            endLng,
            color:
              arc.score >= 0.7
                ? "#00E5CC"
                : arc.score >= 0.5
                  ? "#00BFA5"
                  : "#00897B",
            stroke: 1 + arc.score * 2,
            label: arc.themeLabel,
          };
        }),
    [coordinationArcs],
  );

  if (dimensions.width === 0) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <span className="text-text-secondary text-sm">Initializing…</span>
      </div>
    );
  }

  return (
    <div className="flex justify-center">
      {/* @ts-expect-error react-globe.gl prop types are loose */}
      <Globe
        ref={globeRef}
        width={dimensions.width}
        height={dimensions.height}
        backgroundColor="rgba(0,0,0,0)"
        globeImageUrl={null}
        showGlobe={true}
        showAtmosphere={true}
        // Brighter atmosphere — tealBright instead of teal, thicker halo
        atmosphereColor="#00BFA5"
        atmosphereAltitude={0.22}
        // Globe surface (ocean) — lifted from near-black to a visible
        // midnight blue with subtle self-illumination and specular shine.
        globeMaterial={{
          color: "#152238",
          emissive: "#0D1828",
          emissiveIntensity: 0.35,
          specular: "#1A3A5C",
          shininess: 15,
        }}
        // Country polygons
        polygonsData={geoData?.features ?? []}
        // Smoothly animate altitude changes on hover enter/exit.
        // Gated on reduced-motion preference — snap instantly when on.
        polygonsTransitionDuration={reducedMotion ? 0 : 250}
        // Slight base altitude lift (0.018) makes the 3D side faces visible,
        // which combined with the teal-tinted polygonSideColor simulates
        // thicker borders without needing non-standard THREE.Line widths.
        // Hover pops countries up dramatically at 0.06.
        polygonAltitude={(d: GeoFeature) => {
          const iso = getIsoCode(d.properties);
          return iso && iso === hoveredIso ? 0.06 : 0.018;
        }}
        polygonCapColor={(d: GeoFeature) => {
          const iso = getIsoCode(d.properties);
          if (iso && iso === hoveredIso) {
            // Hover highlight — swap fill to tealMax for an unmistakable
            // glow. Overrides whatever deviation color would normally apply.
            return "#00E5CC";
          }
          return getCountryColor(iso, viewMode, activityByIso);
        }}
        // Polygon "sides" — the vertical faces of the extruded country shape.
        // Tint with a muted teal so the edge reads as part of the border glow
        // rather than a dark seam. This creates the illusion of a thicker
        // border since WebGL THREE.Line widths are hardcoded to 1px.
        polygonSideColor={() => "rgba(0, 191, 165, 0.45)"}
        polygonStrokeColor={(d: GeoFeature) => {
          const iso = getIsoCode(d.properties);
          return iso && iso === hoveredIso
            ? "#FFFFFF" // hovered: pure white for maximum contrast
            : "#00E5CC"; // default: bright tealMax at full opacity — bold borders against dark country fill
        }}
        polygonLabel={(d: GeoFeature) => {
          const iso = getIsoCode(d.properties);
          if (!iso) return "";
          const activity = activityByIso.get(iso);
          if (!activity) {
            return `<div style="background:#161819;padding:6px 10px;border-radius:6px;color:#9E9E9E;font-size:12px;">Not monitored</div>`;
          }
          const totalToday = activity.domestic.today + activity.international.today;
          const ratio =
            viewMode === "DOMESTIC"
              ? activity.domestic.ratio
              : viewMode === "INTERNATIONAL"
                ? activity.international.ratio
                : Math.max(activity.domestic.ratio, activity.international.ratio);
          const coldStartTag = activity.coldStart
            ? `<div style="color:#00E5CC;font-size:10px;margin-top:2px;">cold start</div>`
            : "";
          return `
            <div style="background:#161819;padding:8px 12px;border-radius:6px;border:1px solid #2A2D32;font-family:ui-sans-serif,system-ui;">
              <div style="color:#fff;font-weight:600;font-size:13px;">${activity.flag} ${activity.name}</div>
              <div style="color:#9E9E9E;font-size:11px;margin-top:2px;">${totalToday} articles · ${ratio}x baseline</div>
              ${coldStartTag}
            </div>
          `;
        }}
        onPolygonClick={(d: unknown) => {
          const feature = d as GeoFeature;
          const iso = getIsoCode(feature.properties);
          if (iso && activityByIso.has(iso)) {
            router.push(`/country/${iso}`);
          }
        }}
        onPolygonHover={(polygon: unknown) => {
          if (polygon) {
            const feature = polygon as GeoFeature;
            setHoveredIso(getIsoCode(feature.properties) ?? null);
          } else {
            setHoveredIso(null);
          }
        }}
        // Coordination arcs
        arcsData={arcData}
        arcColor="color"
        arcStroke="stroke"
        arcDashLength={0.4}
        arcDashGap={0.2}
        arcDashAnimateTime={3000}
        arcAltitude={0.25}
        arcLabel="label"
      />
    </div>
  );
}
