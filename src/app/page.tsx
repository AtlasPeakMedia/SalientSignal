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

  // B7: Derive latestDate from the actual country_activity rows instead of
  // new Date(). The data adapter stamps row.latestDate onto each CountryActivity
  // from the Supabase query's most-recent-date keying, so we can read it off
  // any row. This is stable across server + client and doesn't drift with
  // the clock.
  const latestDate = (() => {
    if (isDummy) {
      // Dummy rows stamp a stable fixture date we can read the same way
      const row = countryActivity[0];
      return row?.latestDate ?? null;
    }
    for (const row of countryActivity) {
      if (row.latestDate) return row.latestDate;
    }
    return null;
  })();

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
