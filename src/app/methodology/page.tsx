import Link from "next/link";
import type { Metadata } from "next";
import Wordmark from "@/components/Brand/Wordmark";
import { requireAuth } from "@/lib/auth";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export const metadata: Metadata = {
  title: "Methodology — SalientSignal",
  description:
    "How SalientSignal classifies state media outlets, computes baselines, and detects coordination.",
};

export default async function MethodologyPage() {
  await requireAuth();

  return (
    <main className="min-h-screen">
      {/* Header */}
      <header className="border-b border-bg-divider">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
          <Wordmark />
          <nav className="flex items-center gap-6 text-sm text-text-secondary">
            <Link href="/" className="hover:text-text-body transition-colors">
              Globe
            </Link>
            <Link
              href="/about"
              className="hover:text-text-body transition-colors"
            >
              About
            </Link>
            <span className="text-mono text-xs px-2 py-1 rounded border border-bg-divider">
              METHODOLOGY
            </span>
          </nav>
        </div>
      </header>

      <article className="max-w-3xl mx-auto px-6 py-16">
        <h1 className="text-4xl font-bold text-white mb-2 tracking-tight">
          Methodology
        </h1>
        <p className="text-sm text-text-secondary mb-10">
          How SalientSignal turns raw GDELT data into a globe. Documented
          here in enough detail that anyone who wants to check our work can.
        </p>

        <nav className="text-sm text-text-secondary mb-10 pb-6 border-b border-bg-divider">
          <ol className="space-y-1">
            <li>1. Data sources</li>
            <li>2. Outlet classification</li>
            <li>3. Audience determination</li>
            <li>4. Baseline methodology</li>
            <li>5. Deviation scoring</li>
            <li>6. Coordination detection</li>
            <li>7. Anti-hallucination validation</li>
            <li>8. What we do NOT do</li>
            <li>9. Known limitations</li>
            <li>10. Why no FVEY</li>
          </ol>
        </nav>

        {/* 1. Data sources */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold text-white mb-4">
            1. Data sources
          </h2>
          <p className="text-text-body leading-relaxed mb-4">
            The primary data source is the{" "}
            <a
              href="https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-tealBright hover:text-accent-tealMax"
            >
              GDELT DOC 2.0 API
            </a>
            , an academic-grade global news monitoring project that indexes
            articles from news outlets in 65+ languages. GDELT provides both
            an article-level query mode (ArtList) and a time-series volume
            mode (TimelineVolRaw). We use both.
          </p>
          <p className="text-text-body leading-relaxed mb-4">
            For the <strong className="text-white">15-month historical
            baseline</strong>, SalientSignal queries GDELT&apos;s TimelineVolRaw
            mode for each of the 300+ state-media outlets in our database over
            Jan 1, 2025 through the present. That gives us per-day publication
            volume per outlet without the 250-result-per-query cap that
            applies to article-level queries. A single backfill run produces
            roughly 135,000 aggregated daily rows covering every
            (country, audience, date) tuple.
          </p>
          <p className="text-text-body leading-relaxed">
            For the <strong className="text-white">hourly live data</strong>,
            the pipeline queries GDELT&apos;s ArtList mode once per hour per
            monitored country, classifies each returned article against our
            outlet database, and writes the new rows to Supabase. For a
            small set of locked-down states (Iran, DPRK, Cuba, Belarus,
            Venezuela, Syria, Nicaragua), the live pipeline also falls back
            to direct domain-level queries because GDELT&apos;s country-level
            filter is empirically unreliable for those regimes.
          </p>
        </section>

        {/* 2. Outlet classification */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold text-white mb-4">
            2. Outlet classification
          </h2>
          <p className="text-text-body leading-relaxed mb-4">
            Our outlet database (<span className="text-mono">outlets.json</span>)
            is manually curated. Every entry documents the outlet&apos;s
            canonical domain, country of origin (ISO 3166-1 alpha-2),
            audience type, name, languages, and whether the outlet is
            directly state-owned or merely state-aligned.
          </p>
          <p className="text-text-body leading-relaxed mb-4">
            Sources we cross-reference when classifying an outlet:
          </p>
          <ul className="list-disc list-outside pl-6 space-y-1 text-text-body mb-4">
            <li>
              <a
                href="https://mediamonitor.dhi.ceu.edu/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent-tealBright hover:text-accent-tealMax"
              >
                State Media Monitor (CEU Democracy Institute)
              </a>{" "}
              — their public database of state-owned vs independent outlets
              is our primary authoritative source.
            </li>
            <li>Wikipedia&apos;s country-specific "Mass media in X" articles</li>
            <li>
              <a
                href="https://www.oananews.org/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent-tealBright hover:text-accent-tealMax"
              >
                OANA
              </a>{" "}
              (Organization of Asia-Pacific News Agencies)
            </li>
            <li>Direct inspection of outlet ownership / government filings where available</li>
          </ul>
          <p className="text-text-body leading-relaxed">
            When an outlet&apos;s classification is ambiguous or unverifiable,
            we omit it entirely rather than guess. Every outlet record
            includes a confidence score from 0.0 to 1.0, and entries below
            0.85 are explicitly flagged as state-aligned rather than
            state-owned.
          </p>
        </section>

        {/* 3. Audience determination */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold text-white mb-4">
            3. Audience determination
          </h2>
          <p className="text-text-body leading-relaxed mb-4">
            Every monitored outlet is assigned an audience type:
          </p>
          <ul className="list-disc list-outside pl-6 space-y-2 text-text-body mb-4">
            <li>
              <strong className="text-white">DOMESTIC</strong> — primary
              output targets citizens of the outlet&apos;s home country in
              the national language. Example: TASS in Russian, Rossiya 1,
              CCTV in Mandarin, Press TV Farsi.
            </li>
            <li>
              <strong className="text-white">INTERNATIONAL</strong> — primary
              output targets foreign audiences, typically in English, Spanish,
              French, Arabic, or other second languages. Example: RT English,
              CGTN, Sputnik, Press TV English, TASS English.
            </li>
            <li>
              <strong className="text-white">DIASPORA</strong> — specifically
              targets expat populations in a particular language for a
              particular country. Example: certain German, Russian, and
              Chinese outlets directed at European immigrant communities.
              DIASPORA rows are merged into INTERNATIONAL for display on the
              globe.
            </li>
          </ul>
          <p className="text-text-body leading-relaxed">
            The outlet classification is the primary signal. A secondary
            classifier uses language and platform signals as a fallback for
            articles from outlets we haven&apos;t manually classified, but
            unknown outlets are excluded from the country_activity aggregates
            so they can&apos;t pollute the baseline.
          </p>
        </section>

        {/* 4. Baseline methodology */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold text-white mb-4">
            4. Baseline methodology
          </h2>
          <p className="text-text-body leading-relaxed mb-4">
            For every (country, audience, date) tuple, SalientSignal computes
            a <strong className="text-white">30-day rolling baseline</strong>{" "}
            from the preceding 30 days of publication volume. That baseline is
            the denominator that makes today&apos;s deviation meaningful:
            <em className="text-text-secondary"> does today&apos;s output
            differ from this country&apos;s own normal</em>, not from some
            global average.
          </p>
          <p className="text-text-body leading-relaxed mb-4">
            The baseline object carries four statistics: mean, standard
            deviation, sample size (days_sampled), and confidence tier:
          </p>
          <ul className="list-disc list-outside pl-6 space-y-1 text-text-body mb-4">
            <li>
              <strong className="text-white">HIGH</strong> — 21+ days of
              history. Produces trustworthy deviation scores.
            </li>
            <li>
              <strong className="text-white">MEDIUM</strong> — 7-20 days of
              history. Trustworthy for directional signal; extreme level
              labels get a caveat.
            </li>
            <li>
              <strong className="text-white">LOW</strong> — fewer than 7
              days. Cold-start mode. Only the raw ratio contributes to
              coloring and extreme levels are suppressed.
            </li>
          </ul>
          <p className="text-text-body leading-relaxed">
            Because we backfilled 15 months of history before launch, every
            date after Jan 30, 2025 has at least a HIGH-confidence 30-day
            baseline behind it. The cold-start window exists in code for
            development and local testing but does NOT appear in the production
            globe.
          </p>
        </section>

        {/* 5. Deviation scoring */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold text-white mb-4">
            5. Deviation scoring
          </h2>
          <p className="text-text-body leading-relaxed mb-4">
            The deviation score combines two signals: the{" "}
            <strong className="text-white">ratio</strong> (today&apos;s count
            divided by the baseline mean) and the{" "}
            <strong className="text-white">z-score</strong> (how many standard
            deviations above or below the baseline mean today sits).
          </p>
          <p className="text-text-body leading-relaxed mb-4">
            We use both signals because neither is sufficient alone. A ratio
            of 2x looks dramatic but isn&apos;t interesting if the outlet
            varies wildly day-to-day — the z-score catches that. Conversely,
            a z-score of 3 with a 1.3x ratio is only meaningful for
            high-volume countries where small percentage changes move huge
            absolute numbers — the ratio check gates that against noise.
          </p>
          <p className="text-text-body leading-relaxed mb-4">
            The level mapping, in priority order:
          </p>
          <ul className="list-disc list-outside pl-6 space-y-1 text-text-body mb-4 text-sm">
            <li>
              <span className="text-red-400">Red (anomalous surge)</span> —
              z-score &ge; 2.5, regardless of ratio.
            </li>
            <li>
              <span className="text-orange-400">Orange (significant spike)</span>{" "}
              — ratio &le; 4.0 AND z-score &ge; 2.0.
            </li>
            <li>
              <span className="text-amber-400">Amber (elevated)</span> — ratio
              &le; 2.5 AND z-score &ge; 1.5.
            </li>
            <li>
              <span className="text-white">Neutral (normal range)</span> —
              ratio 0.75 to 1.5, no significant z-score.
            </li>
            <li>
              <span className="text-blue-400">Cool gray (slightly below)</span>{" "}
              — ratio below 0.75.
            </li>
            <li>
              <span className="text-blue-400">Steel blue (unusually quiet)</span>{" "}
              — ratio below 0.5 AND z-score below -1.5.
            </li>
            <li>
              <span className="text-blue-500">Deep blue (significant silence)</span>{" "}
              — ratio below 0.3 AND z-score below -2.0.
            </li>
          </ul>
          <p className="text-text-body leading-relaxed">
            Silence is a signal too. A country that normally publishes 500
            articles a day dropping to 50 articles a day is often more
            interesting than a country that spikes upward — the silent one
            may be trying to avoid talking about something.
          </p>
        </section>

        {/* 6. Coordination detection */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold text-white mb-4">
            6. Coordination detection
          </h2>
          <p className="text-text-body leading-relaxed mb-4">
            The arc lines on the globe represent detected cross-country
            coordination events. An arc appears when two or more countries
            show a simultaneous spike on the same GDELT theme within a
            24-hour window, AND the arc&apos;s coordination score clears a
            confidence threshold.
          </p>
          <p className="text-text-body leading-relaxed mb-4">
            The score combines four factors: baseline deviation strength
            (how significant is the spike?), theme overlap (do the
            countries actually talk about the same thing?), temporal
            tightness (how close together were the spikes?), and country
            co-occurrence history (does this pair of countries coordinate
            often enough that today&apos;s pairing is noise?).
          </p>
          <p className="text-text-body leading-relaxed">
            <strong className="text-white">Important limitation:</strong>{" "}
            coordination detection in the MVP is relatively crude. Real
            coordinated information operations involve more than a
            simultaneous theme spike; they involve message synchronization,
            shared source material, and cross-platform amplification. The
            MVP detects the easy cases (obvious simultaneous themes from
            the usual suspects) and the hard cases are deferred to Phase B
            of the anti-hallucination agent work.
          </p>
        </section>

        {/* 7. Anti-hallucination validation */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold text-white mb-4">
            7. Anti-hallucination validation
          </h2>
          <p className="text-text-body leading-relaxed mb-4">
            Every claim the pipeline produces — a classification, a
            deviation score, a coordination event — passes through an
            Anti-Hallucination Agent before being published. The agent
            applies Structured Analytic Techniques from the IC analysts&apos;
            handbook (Heuer &amp; Pherson) to test whether the claim is
            supported by the underlying data.
          </p>
          <p className="text-text-body leading-relaxed mb-4">
            Each claim receives one of five verdicts:
          </p>
          <ul className="list-disc list-outside pl-6 space-y-1 text-text-body mb-4">
            <li>
              <strong className="text-white">PUBLISH</strong> — high
              confidence, all tests pass
            </li>
            <li>
              <strong className="text-white">PUBLISH_WITH_CAVEAT</strong> —
              true but hedged (e.g. "medium confidence due to small sample")
            </li>
            <li>
              <strong className="text-white">SUPPRESS</strong> — alternative
              explanations not ruled out (anniversary coverage, wire service
              syndication, timezone artifact)
            </li>
            <li>
              <strong className="text-white">ESCALATE</strong> — high impact
              (e.g. 4+ country coordination) and requires human review
              before display
            </li>
            <li>
              <strong className="text-white">PERSISTED_TO_AUDIT</strong> —
              every claim, regardless of verdict, lands in the
              analysis_claims table for after-the-fact review
            </li>
          </ul>
          <p className="text-text-body leading-relaxed">
            The agent deliberately errs on the side of suppression.
            Incorrect publication is embarrassing; incorrect suppression is
            invisible and fixable in the next run. The agent&apos;s
            judgment list (anniversaries, generic themes, small-sample
            cold-start windows) is documented in the pipeline source
            under <span className="text-mono">src/antihal.py</span>.
          </p>
        </section>

        {/* 8. What we do NOT do */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold text-white mb-4">
            8. What we do NOT do
          </h2>
          <ul className="list-disc list-outside pl-6 space-y-3 text-text-body">
            <li>
              <strong className="text-white">
                We do not label anything as propaganda, disinformation, or
                misinformation.
              </strong>{" "}
              The product measures what state media publishes and how much
              of it. What it means is your job.
            </li>
            <li>
              <strong className="text-white">
                We do not generate AI analysis in the MVP.
              </strong>{" "}
              No automated debrief paragraphs, no "here&apos;s what this
              means" commentary. That&apos;s a planned post-launch feature
              behind its own anti-hallucination guardrails, but it&apos;s
              not shipped yet.
            </li>
            <li>
              <strong className="text-white">
                We do not claim intent.
              </strong>{" "}
              A coordination arc means "these countries&apos; state media
              simultaneously spiked the same theme." It does NOT mean "these
              countries are coordinating." Causation is a claim; correlation
              is what we measure.
            </li>
            <li>
              <strong className="text-white">
                We do not monitor private citizens, private accounts, or
                private platforms.
              </strong>{" "}
              Only public outlets with registered domains and
              internationally-recognized state-ownership status.
            </li>
          </ul>
        </section>

        {/* 9. Known limitations */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold text-white mb-4">
            9. Known limitations
          </h2>
          <ul className="list-disc list-outside pl-6 space-y-3 text-text-body">
            <li>
              <strong className="text-white">GDELT has a Western source bias.</strong>{" "}
              Its documented accuracy on key fields is around 55%, and
              Western news agencies are over-represented in its crawl. A
              country appearing "quiet" on our globe may simply be
              under-covered by GDELT rather than actually publishing less.
              We work around this via direct domain queries for locked-down
              states, but the bias is real and persistent.
            </li>
            <li>
              <strong className="text-white">
                Locked-down states have partial coverage.
              </strong>{" "}
              GDELT&apos;s sourcecountry filter returns essentially nothing
              for Iran, North Korea, Cuba, and Belarus. We compensate with
              a per-outlet fallback path, but our coverage of those regimes
              still depends on which specific outlet domains GDELT crawls
              at all.
            </li>
            <li>
              <strong className="text-white">
                Translation quality varies.
              </strong>{" "}
              We do NOT translate content; we display whatever language
              the outlet publishes in. Article titles in non-Latin scripts
              appear as-is on the country page.
            </li>
            <li>
              <strong className="text-white">
                Top themes are not populated for historical dates.
              </strong>{" "}
              The 15-month backfill captured daily publication volume but
              did NOT capture article-level themes, because that would have
              required thousands of additional queries. Historical country
              pages show the baseline and deviation, but the "top themes"
              list will be sparse until the live pipeline has accumulated
              enough data.
            </li>
            <li>
              <strong className="text-white">
                The classifier is deterministic, not probabilistic.
              </strong>{" "}
              An outlet is DOMESTIC, INTERNATIONAL, or DIASPORA — there&apos;s
              no "probably domestic" middle ground. Outlets with mixed
              audiences (e.g. CGTN English, which serves both the Chinese
              diaspora AND foreign audiences) are assigned to their primary
              bucket and the secondary signal is lost.
            </li>
          </ul>
        </section>

        {/* 10. Why no FVEY */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold text-white mb-4">
            10. Why no FVEY
          </h2>
          <p className="text-text-body leading-relaxed mb-4">
            SalientSignal explicitly excludes state and state-aligned media
            from the Five Eyes intelligence alliance: the United States,
            United Kingdom, Canada, Australia, and New Zealand. FVEY
            countries are filtered out at both the source database level
            (their outlets are not in <span className="text-mono">outlets.json</span>)
            and the pipeline level (the import script rejects any row with
            a FVEY ISO code as a validation failure).
          </p>
          <p className="text-text-body leading-relaxed mb-4">
            This is a scope decision, not a political one. The product is
            for understanding foreign state media. Mixing in US and UK
            public broadcasters would dilute that signal, and there are
            already excellent tools monitoring Western media output.
          </p>
          <p className="text-text-body leading-relaxed">
            The exclusion is hardcoded and not subject to request. If your
            use case requires Western state media monitoring, there are
            other products.
          </p>
        </section>

        <div className="border-t border-bg-divider pt-8 mt-12 text-sm text-text-secondary">
          <p>
            Questions, corrections, or disputes about this methodology
            should go to{" "}
            <span className="text-mono">hello@atlaspeakmedia.com</span>.
            Version 1.0 / April 2026.
          </p>
        </div>
      </article>

      {/* Footer */}
      <footer className="max-w-[1400px] mx-auto px-6 py-6 text-xs text-text-secondary border-t border-bg-divider">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span>Atlas Peak Media, LLC · US/FVEY excluded</span>
          <Link
            href="/"
            className="text-mono hover:text-text-body transition-colors"
          >
            ← Back to globe
          </Link>
        </div>
      </footer>
    </main>
  );
}
