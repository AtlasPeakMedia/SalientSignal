"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  COUNTRY_ACTIVITY,
  COORDINATION_ARCS,
  type CountryActivity,
} from "@/lib/dummy-data";
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
}

// Lookup map for fast color resolution
const ACTIVITY_BY_ISO = new Map<string, CountryActivity>(
  COUNTRY_ACTIVITY.map((c) => [c.iso2, c])
);

function getCountryColor(isoA2: string | undefined, viewMode: ViewMode): string {
  if (!isoA2) return "#1A1D24";
  const activity = ACTIVITY_BY_ISO.get(isoA2);
  if (!activity) return "#1A1D24"; // Unmonitored country = neutral

  let level: CountryActivity["domestic"]["level"];
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

// Lat/lng for arc endpoints — approximate centroids
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
};

export default function GlobeWrapper({ viewMode }: Props) {
  const router = useRouter();
  const globeRef = useRef<unknown>(null);
  const [geoData, setGeoData] = useState<GeoJson | null>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  useEffect(() => {
    fetch("/data/ne_110m_admin_0_countries.geojson")
      .then((r) => r.json())
      .then((data: GeoJson) => setGeoData(data))
      .catch(() => {
        // GeoJSON not yet downloaded — Globe will show empty
        console.warn("Country boundaries not loaded. Run scripts/fetch-geojson.sh");
      });
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

  // Build arc data with lat/lng coordinates
  const arcData = COORDINATION_ARCS.filter(
    (arc) => COUNTRY_CENTROIDS[arc.startIso] && COUNTRY_CENTROIDS[arc.endIso]
  ).map((arc) => {
    const [startLat, startLng] = COUNTRY_CENTROIDS[arc.startIso];
    const [endLat, endLng] = COUNTRY_CENTROIDS[arc.endIso];
    return {
      startLat,
      startLng,
      endLat,
      endLng,
      color:
        arc.score >= 0.7 ? "#00E5CC" : arc.score >= 0.5 ? "#00BFA5" : "#00897B",
      stroke: 1 + arc.score * 2,
      label: arc.themeLabel,
    };
  });

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
        atmosphereColor="#00897B"
        atmosphereAltitude={0.15}
        // Globe surface (ocean)
        globeMaterial={{
          color: "#0A0F1A",
          emissive: "#0A0F1A",
          shininess: 0,
        }}
        // Country polygons
        polygonsData={geoData?.features ?? []}
        polygonAltitude={0.01}
        polygonCapColor={(d: GeoFeature) =>
          getCountryColor(getIsoCode(d.properties), viewMode)
        }
        polygonSideColor={() => "rgba(20, 20, 25, 0.5)"}
        polygonStrokeColor={() => "#0A0F1A"}
        polygonLabel={(d: GeoFeature) => {
          const iso = getIsoCode(d.properties);
          if (!iso) return "";
          const activity = ACTIVITY_BY_ISO.get(iso);
          if (!activity) {
            return `<div style="background:#161819;padding:6px 10px;border-radius:6px;color:#9E9E9E;font-size:12px;">Not monitored</div>`;
          }
          const ratio =
            viewMode === "DOMESTIC"
              ? activity.domestic.ratio
              : viewMode === "INTERNATIONAL"
                ? activity.international.ratio
                : Math.max(activity.domestic.ratio, activity.international.ratio);
          return `
            <div style="background:#161819;padding:8px 12px;border-radius:6px;border:1px solid #2A2D32;font-family:ui-sans-serif,system-ui;">
              <div style="color:#fff;font-weight:600;font-size:13px;">${activity.flag} ${activity.name}</div>
              <div style="color:#9E9E9E;font-size:11px;margin-top:2px;">${ratio}x baseline</div>
            </div>
          `;
        }}
        onPolygonClick={(d: unknown) => {
          const feature = d as GeoFeature;
          const iso = getIsoCode(feature.properties);
          if (iso && ACTIVITY_BY_ISO.has(iso)) {
            router.push(`/country/${iso}`);
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
