import Link from "next/link";
import { notFound } from "next/navigation";
import Wordmark from "@/components/Brand/Wordmark";
import {
  getCountryActivity,
  getCountryHeadlines,
  type AudienceType,
} from "@/lib/dummy-data";
import { DEVIATION_COLORS, DEVIATION_LABELS } from "@/lib/colors";

interface PageProps {
  params: Promise<{ code: string }>;
}

export default async function CountryPage({ params }: PageProps) {
  const { code } = await params;
  const country = getCountryActivity(code);
  if (!country) notFound();

  const headlines = getCountryHeadlines(code);
  const domestic = headlines.filter((h) => h.audienceType === "DOMESTIC");
  const international = headlines.filter((h) => h.audienceType === "INTERNATIONAL");

  return (
    <main className="min-h-screen">
      {/* Header */}
      <header className="border-b border-bg-divider">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
          <Wordmark />
          <Link
            href="/"
            className="text-sm text-text-secondary hover:text-text-body transition-colors"
          >
            ← Back to globe
          </Link>
        </div>
      </header>

      {/* Country header */}
      <section className="max-w-[1400px] mx-auto px-6 py-8">
        <div className="flex items-center gap-4 mb-2">
          <span className="text-5xl">{country.flag}</span>
          <div>
            <h1 className="text-3xl font-bold text-white">{country.name}</h1>
            <p className="text-sm text-text-secondary">{country.region}</p>
          </div>
        </div>
        <p className="text-sm text-text-body max-w-3xl mt-3">
          State media activity for{" "}
          {new Date().toLocaleDateString("en-US", {
            weekday: "long",
            year: "numeric",
            month: "long",
            day: "numeric",
          })}
          . Compare what {country.name}'s state outlets are publishing for domestic
          audiences versus international audiences. Baselines are 30-day rolling
          averages.
        </p>
      </section>

      {/* Audience split */}
      <section className="max-w-[1400px] mx-auto px-6 grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <AudienceColumn
          audience="DOMESTIC"
          activity={country.domestic}
          headlines={domestic}
        />
        <AudienceColumn
          audience="INTERNATIONAL"
          activity={country.international}
          headlines={international}
        />
      </section>

      {/* Footer */}
      <footer className="max-w-[1400px] mx-auto px-6 py-6 text-xs text-text-secondary border-t border-bg-divider">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span>
            Source: GDELT 2.0 + monitored RSS feeds · State media classification
            from State Media Monitor (CEU)
          </span>
          <span className="text-mono">DEMO DATA</span>
        </div>
      </footer>
    </main>
  );
}

interface AudienceColumnProps {
  audience: AudienceType;
  activity: ReturnType<typeof getCountryActivity> extends infer T
    ? T extends { domestic: infer D }
      ? D
      : never
    : never;
  headlines: ReturnType<typeof getCountryHeadlines>;
}

function AudienceColumn({ audience, activity, headlines }: AudienceColumnProps) {
  const isDomestic = audience === "DOMESTIC";
  const label = isDomestic ? "Domestic Audience" : "International Audience";
  const sublabel = isDomestic
    ? "Outlets targeting the country's own population"
    : "Outlets targeting foreign audiences in non-native languages";

  const color = DEVIATION_COLORS[activity.level];
  const levelLabel = DEVIATION_LABELS[activity.level];

  return (
    <div className="card p-6">
      {/* Header */}
      <div className="flex items-start justify-between mb-5 pb-4 border-b border-bg-divider">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: color }}
            />
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
              {label}
            </h2>
          </div>
          <p className="text-xs text-text-secondary">{sublabel}</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <Stat label="Today" value={activity.today.toString()} />
        <Stat label="Baseline" value={activity.baseline.toString()} />
        <Stat
          label="Ratio"
          value={`${activity.ratio}x`}
          highlight={
            activity.ratio > 1.5
              ? "amber"
              : activity.ratio < 0.7
                ? "blue"
                : "neutral"
          }
        />
      </div>

      {/* Status pill */}
      <div className="mb-6">
        <div
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border"
          style={{
            backgroundColor: `${color}22`,
            borderColor: `${color}44`,
            color: color,
          }}
        >
          <span>{levelLabel}</span>
          <span className="text-mono opacity-75">z-score {activity.zScore}</span>
        </div>
      </div>

      {/* Headlines */}
      <div>
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
          Recent Headlines
        </h3>
        {headlines.length === 0 ? (
          <div className="text-sm text-text-secondary italic py-6 text-center border border-dashed border-bg-divider rounded-md">
            No headlines available for demo. Will populate when pipeline is live.
          </div>
        ) : (
          <ul className="space-y-3">
            {headlines.map((h, idx) => (
              <li
                key={idx}
                className="border-l-2 border-bg-divider pl-3 hover:border-accent-teal transition-colors"
              >
                <div className="flex items-center gap-2 text-xs text-text-secondary mb-1">
                  <span className="text-mono uppercase">{h.outlet}</span>
                  <span>·</span>
                  <span className="text-mono uppercase">{h.outletLanguage}</span>
                </div>
                <p className="text-sm text-text-body leading-snug">{h.title}</p>
                {h.themes.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {h.themes.map((t) => (
                      <span
                        key={t}
                        className="text-[10px] text-accent-tealBright bg-bg-base px-1.5 py-0.5 rounded text-mono uppercase tracking-wider"
                      >
                        {t.toLowerCase().replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  highlight = "neutral",
}: {
  label: string;
  value: string;
  highlight?: "amber" | "blue" | "neutral";
}) {
  const colors = {
    amber: "text-amber-400",
    blue: "text-blue-400",
    neutral: "text-white",
  };
  return (
    <div>
      <div className="text-xs text-text-secondary uppercase tracking-wider mb-1">
        {label}
      </div>
      <div className={`text-2xl font-semibold text-mono ${colors[highlight]}`}>
        {value}
      </div>
    </div>
  );
}
