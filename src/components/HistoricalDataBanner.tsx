/**
 * HistoricalDataBanner — shown on the home page when the data source is
 * either (a) the dummy fixture (developer preview) or (b) the live Supabase
 * data but the latest ingested date is more than ~24 hours stale.
 *
 * Phase D16 rename: this component was previously ColdStartBanner, which
 * explained the 21-day baseline warm-up period. That warm-up no longer
 * exists because Phase A of the backfill plan pulls 15 months of GDELT
 * history and computes real baselines before launch. The banner still
 * serves as the "data provenance" label at the top of the page, but it
 * says "Live Intelligence Data" now, not "Baseline calibration".
 *
 * When to show:
 *   - isDummy=true           → show with "Preview data" language
 *   - isStale=true            → show with "Stale data" language (pipeline
 *                                haven't posted a row in >24h)
 *   - Otherwise               → hide. The data is fresh and trustworthy.
 *
 * The banner is deliberately low-urgency (matches the dark academia palette)
 * because these are status signals, not errors.
 */

interface Props {
  /** True when the page is rendering against the dummy fixture. */
  isDummy?: boolean;
  /**
   * True when the most-recent country_activity date is more than 24 hours
   * old. Indicates the hourly pipeline cron hasn't run (Render outage, etc.)
   */
  isStale?: boolean;
  /** Master visibility switch. When false, nothing renders regardless of other flags. */
  show: boolean;
}

export default function HistoricalDataBanner({
  isDummy = false,
  isStale = false,
  show,
}: Props) {
  if (!show) return null;

  // Precedence: dummy > stale > live-historical.
  // Only one label renders so the banner stays single-line on mobile.
  let label: string;
  let message: string;

  if (isDummy) {
    label = "Preview data";
    message =
      "You're looking at the demo fixture. Set NEXT_PUBLIC_USE_DUMMY_DATA=false " +
      "to render against the live Supabase data.";
  } else if (isStale) {
    label = "Stale data";
    message =
      "The hourly pipeline hasn't posted a new row in over 24 hours. " +
      "Baselines and deviations are accurate as of the last successful run.";
  } else {
    label = "Live intelligence data";
    message =
      "Baselines computed from 15 months of GDELT historical data (Jan 2025 – present). " +
      "Deviation metrics are production-ready.";
  }

  return (
    <div
      role="status"
      className="border-b border-bg-divider bg-bg-raised/40 text-xs"
    >
      <div className="max-w-[1400px] mx-auto px-6 py-2.5 flex flex-wrap items-center gap-x-3 gap-y-1">
        <span
          aria-hidden="true"
          className="inline-block h-1.5 w-1.5 rounded-full bg-accent-tealBright animate-pulse"
        />
        <span className="text-text-body font-medium uppercase tracking-wider">
          {label}
        </span>
        <span className="text-text-secondary">{message}</span>
      </div>
    </div>
  );
}
