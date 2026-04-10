import Link from "next/link";
import type { Metadata } from "next";
import Wordmark from "@/components/Brand/Wordmark";
import { requireAuth } from "@/lib/auth";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export const metadata: Metadata = {
  title: "About — SalientSignal",
  description:
    "Foreign media intelligence from 300+ state-run outlets across 80+ countries. Built by Atlas Peak Media.",
};

export default async function AboutPage() {
  await requireAuth();

  return (
    <main className="min-h-screen">
      {/* Header */}
      <header className="border-b border-bg-divider">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
          <Wordmark />
          <nav className="flex items-center gap-6 text-sm text-text-secondary">
            <Link
              href="/"
              className="hover:text-text-body transition-colors"
            >
              Globe
            </Link>
            <Link
              href="/methodology"
              className="hover:text-text-body transition-colors"
            >
              Methodology
            </Link>
            <span className="text-mono text-xs px-2 py-1 rounded border border-bg-divider">
              ABOUT
            </span>
          </nav>
        </div>
      </header>

      {/* Content */}
      <article className="max-w-3xl mx-auto px-6 py-16 prose-invert">
        <h1 className="text-4xl font-bold text-white mb-6 tracking-tight">
          About SalientSignal
        </h1>

        <p className="text-lg text-text-body leading-relaxed mb-6">
          SalientSignal watches what state-run media around the world is
          publishing, and what it&apos;s NOT publishing. The product compares
          each country&apos;s output today against its own 30-day baseline,
          computed from 15 months of historical data, and surfaces the signal
          on an interactive globe.
        </p>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3 mt-8">
            Why this exists
          </h2>
          <p className="text-text-body leading-relaxed mb-4">
            Hamilton 2.0, the Alliance for Securing Democracy&apos;s
            state-media tracker, shut down in 2022. The State Department&apos;s
            Global Engagement Center (GEC) was defunded in 2024. Between them,
            roughly a decade of public foreign-media monitoring infrastructure
            came offline in two years.
          </p>
          <p className="text-text-body leading-relaxed mb-4">
            The practitioners who used those tools — disinformation reporters,
            open-source analysts, policy researchers, intelligence students,
            and (quietly) a lot of government workers — still need the data.
            SalientSignal fills part of the vacuum with a free, public, always-
            on replacement for the daily "what is Russian/Chinese/Iranian
            state media saying today" question.
          </p>
          <p className="text-text-body leading-relaxed">
            The core observation behind the product: the most interesting
            signal isn&apos;t the volume of what regimes publish — it&apos;s
            the divergence between what they say to their own citizens and
            what they say to foreign audiences. That split is the primary
            view on the globe.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3 mt-8">
            What we monitor
          </h2>
          <ul className="list-disc list-outside pl-6 space-y-2 text-text-body">
            <li>
              <strong className="text-white">300+ state-run outlets</strong>{" "}
              across 80+ countries, ranging from the big four (Russia, China,
              Iran, DPRK) through Gulf state media, post-Soviet republics,
              Sub-Saharan African public broadcasters, and everything else in
              between.
            </li>
            <li>
              <strong className="text-white">Domestic and international
              audiences separately</strong> — TASS in Russian is a different
              signal than TASS in English. Same outlet, different message.
            </li>
            <li>
              <strong className="text-white">Publication volume, not
              tone.</strong> We&apos;re not trying to label anything as
              propaganda or disinformation. We measure how much of something
              is being said. The interpretation is up to you.
            </li>
            <li>
              <strong className="text-white">No Five Eyes coverage.</strong>{" "}
              We deliberately exclude US, UK, Canadian, Australian, and New
              Zealand outlets. This is foreign media intelligence. Our own
              side is somebody else&apos;s problem.
            </li>
          </ul>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3 mt-8">
            Who built this
          </h2>
          <p className="text-text-body leading-relaxed">
            SalientSignal is built and operated by{" "}
            <strong className="text-white">Atlas Peak Media, LLC</strong>, a
            small independent publisher. We own the whole stack — the
            pipeline, the classification rules, the globe, the dashboard —
            so there&apos;s nobody upstream who can decide to shut the
            product off or repurpose the data.
          </p>
          <p className="text-text-body leading-relaxed mt-4">
            No government funding. No venture capital. No outside board.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3 mt-8">
            How it&apos;s funded
          </h2>
          <p className="text-text-body leading-relaxed">
            The core view — today&apos;s globe, country pages, baseline
            deviations — is free forever, for everyone. Future paid tiers
            will cover things like AI-generated daily briefings, the
            historical archive explorer, API access, and custom alerting.
            The free tier is what everyone needs; the paid tier is for
            organizations that need more.
          </p>
          <p className="text-text-body leading-relaxed mt-4">
            US military personnel with a .mil email address will get full
            paid features free. The last generation of foreign-media
            monitoring tools was mostly built inside the government. The
            hand-off between those tools and the private replacements has
            been rough, and we don&apos;t want the Marines running a
            Facebook Crowdtangle clone from an Excel sheet.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3 mt-8">
            Methodology, not editorial
          </h2>
          <p className="text-text-body leading-relaxed">
            SalientSignal does not write analysis or take editorial positions.
            We publish the data, document how we produced it, and let
            analysts, reporters, and students draw their own conclusions. The{" "}
            <Link
              href="/methodology"
              className="text-accent-tealBright hover:text-accent-tealMax transition-colors"
            >
              Methodology page
            </Link>{" "}
            is the source of truth for how outlets are classified, how
            baselines are computed, and what the product does NOT do.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3 mt-8">
            Contact
          </h2>
          <p className="text-text-body leading-relaxed">
            Bug reports, corrections, outlet classification fixes, or press
            inquiries: <span className="text-mono">hello@atlaspeakmedia.com</span>
          </p>
          <p className="text-text-body leading-relaxed mt-4 text-sm text-text-secondary">
            We don&apos;t respond to requests from adversarial researchers
            asking for help classifying our pipeline. Sorry.
          </p>
        </section>
      </article>

      {/* Footer */}
      <footer className="max-w-[1400px] mx-auto px-6 py-6 text-xs text-text-secondary border-t border-bg-divider">
        <div className="flex items-center justify-end">
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
