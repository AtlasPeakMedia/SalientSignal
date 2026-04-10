import HomePageClient from "./HomePageClient";
import {
  getAllCountryActivity,
  getCoordinationArcs,
  getTrendingThemes,
  isUsingDummyData,
} from "@/lib/data";

// Re-fetch every 5 minutes — the cron pipeline only updates hourly, so
// stale-for-5-minutes is an acceptable tradeoff for edge caching.
export const revalidate = 300;

export default async function HomePage() {
  const [countryActivity, coordinationArcs, trendingThemes] = await Promise.all([
    getAllCountryActivity(),
    getCoordinationArcs(),
    getTrendingThemes(),
  ]);

  const isDummy = isUsingDummyData();
  const coldStartCount = countryActivity.filter((c) => c.coldStart).length;

  // The "latest date" is whatever the data layer returned — infer from the
  // most recent cold-start flag flip. For the demo path we just use today.
  const latestDate = isDummy
    ? null
    : new Date().toISOString().slice(0, 10);

  return (
    <HomePageClient
      countryActivity={countryActivity}
      coordinationArcs={coordinationArcs}
      trendingThemes={trendingThemes}
      isDummy={isDummy}
      latestDate={latestDate}
      coldStartCount={coldStartCount}
    />
  );
}
