/**
 * ColdStartBanner — explains why the globe looks muted during the first ~3
 * weeks of pipeline operation. Shown at the top of the home page when any
 * country in the current dataset is still inside its baseline warm-up window.
 *
 * The banner is deliberately low-urgency (matches the dark academia palette)
 * because cold start is a feature, not an error — we don't have enough history
 * to compute a reliable 30-day baseline yet, and publishing anomaly flags
 * without that baseline would be dishonest.
 */

interface Props {
  daysCollected?: number;
  show: boolean;
}

export default function ColdStartBanner({ daysCollected, show }: Props) {
  if (!show) return null;

  const daysPhrase =
    typeof daysCollected === "number" && daysCollected > 0
      ? ` (${daysCollected} of 21 days collected)`
      : "";

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
          Baseline calibration
        </span>
        <span className="text-text-secondary">
          Pipeline is warming up{daysPhrase}. Countries are shown in neutral
          tones until the 30-day rolling baseline stabilizes around day 21.
        </span>
      </div>
    </div>
  );
}
