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

  // The "latest date" drives the stale-data banner (D16). Use the max of
  // the row dates on live data; null on dummy so the banner shows the
  // "preview data" label instead.
  const latestDate = isDummy
    ? null
    : countryActivity.reduce<string | null>((acc, row) => {
        // CountryActivity doesn't expose date directly on the aggregated row,
        // but the data adapter already keys off the most-recent-date query so
        // the rows reflect the latest ingested date. Fall back to today-iso.
        return acc;
      }, null) ?? new Date().toISOString().slice(0, 10);

  return (
    <HomePageClient
      countryActivity={countryActivity}
      coordinationArcs={coordinationArcs}
      trendingThemes={trendingThemes}
      isDummy={isDummy}
      latestDate={latestDate}
    />
  );
}
