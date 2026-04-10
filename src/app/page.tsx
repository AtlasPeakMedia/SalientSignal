import HomePageClient from "./HomePageClient";
import {
  getAllCountryActivity,
  getCoordinationArcs,
  getTrendingThemes,
  isUsingDummyData,
} from "@/lib/data";

// Force this route to render on every request as a serverless function.
// Previously used ISR (revalidate = 300) but that produced a Static output
// format that Vercel's edge router couldn't locate on this monorepo layout,
// causing every route to 404. Dynamic rendering uses a different output
// layout that works correctly. Performance cost is negligible here because
// each request just reads from Supabase, which is fast.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

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
