import HomePageClient from "./HomePageClient";
import {
  getAllCountryActivity,
  getCoordinationArcs,
  getTrendingThemes,
  isUsingDummyData,
} from "@/lib/data";
import { requireAuth } from "@/lib/auth";

// Force this route to render on every request as a serverless function.
// Dynamic rendering uses the same Node.js function layout as the other
// routes, avoiding any static-output routing quirks.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export default async function HomePage() {
  // Pre-launch password gate. Redirects to /login if the user doesn't
  // have a valid ss_auth cookie. Throws a Next.js redirect which
  // terminates rendering before any data fetching happens.
  await requireAuth();

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
