import Link from "next/link";
import type { Metadata } from "next";
import Wordmark from "@/components/Brand/Wordmark";
import { requireAuth } from "@/lib/auth";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export const metadata: Metadata = {
  title: "Terms of Service — SalientSignal",
  description:
    "Terms of service for SalientSignal. Free intelligence product with no warranty of fitness for any particular analytical use.",
};

export default async function TermsPage() {
  await requireAuth();

  return (
    <main className="min-h-screen">
      <header className="border-b border-bg-divider">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
          <Wordmark />
          <nav className="flex items-center gap-6 text-sm text-text-secondary">
            <Link href="/" className="hover:text-text-body transition-colors">
              Globe
            </Link>
            <Link
              href="/methodology"
              className="hover:text-text-body transition-colors"
            >
              Methodology
            </Link>
            <Link
              href="/about"
              className="hover:text-text-body transition-colors"
            >
              About
            </Link>
            <span className="text-mono text-xs px-2 py-1 rounded border border-bg-divider">
              TERMS
            </span>
          </nav>
        </div>
      </header>

      <article className="max-w-3xl mx-auto px-6 py-16">
        <h1 className="text-4xl font-bold text-white mb-2 tracking-tight">
          Terms of Service
        </h1>
        <p className="text-sm text-text-secondary mb-10">
          Plain-English terms. No warranty, no indemnity, no legal liability
          for analytical decisions made on top of this data.
        </p>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3">
            1. What SalientSignal is
          </h2>
          <p className="text-text-body leading-relaxed">
            SalientSignal is a free-to-use, read-only foreign media
            monitoring product operated by Atlas Peak Media, LLC ("we",
            "us"). It publishes aggregated daily publication volume data
            for 300+ state-run media outlets across 80+ countries, drawn
            primarily from the GDELT Project&apos;s public DOC 2.0 API.
            The product is intended for analysts, reporters, academics,
            researchers, and policy staff who need a machine-assisted view
            of foreign state media activity.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3">
            2. No warranty of accuracy or fitness
          </h2>
          <p className="text-text-body leading-relaxed mb-4">
            The data presented on SalientSignal is provided{" "}
            <strong className="text-white">AS IS</strong>, with{" "}
            <strong className="text-white">NO WARRANTY</strong> of accuracy,
            completeness, fitness for a particular purpose, or
            non-infringement. In particular:
          </p>
          <ul className="list-disc list-outside pl-6 space-y-2 text-text-body">
            <li>
              Outlet classifications are manually curated and may contain
              errors. We correct errors when notified (see Privacy page)
              but make no guarantee of correctness.
            </li>
            <li>
              GDELT&apos;s coverage is incomplete for countries with
              restricted press environments. The <em>absence</em> of a
              deviation signal does not imply the absence of an actual
              publication event.
            </li>
            <li>
              Baselines, deviation scores, and coordination arcs are
              algorithmic outputs, not journalistic claims. They indicate
              anomaly probability, not confirmed facts.
            </li>
            <li>
              Headlines and article metadata are surfaced from GDELT and
              displayed in their original language. We do not verify,
              translate, or fact-check them.
            </li>
          </ul>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3">
            3. Not analysis. Not intelligence product.
          </h2>
          <p className="text-text-body leading-relaxed">
            SalientSignal is a{" "}
            <strong className="text-white">data aggregation tool</strong>,
            not an analytical product. The{" "}
            <Link
              href="/methodology"
              className="text-accent-tealBright hover:text-accent-tealMax"
            >
              Methodology page
            </Link>{" "}
            explicitly enumerates what we do NOT do: we do not label
            anything as propaganda, disinformation, or misinformation;
            we do not generate AI analysis in the MVP; we do not claim
            intent; we do not monitor private individuals. Nothing on
            this site should be cited as evidence of anyone&apos;s
            motives, beliefs, or planned actions.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3">
            4. Permitted use
          </h2>
          <p className="text-text-body leading-relaxed mb-4">
            You may use SalientSignal for any lawful purpose: research,
            journalism, academic work, government analysis, private
            curiosity. You may cite the site, link to it, and screenshot
            it for editorial use with attribution to Atlas Peak Media,
            LLC.
          </p>
          <p className="text-text-body leading-relaxed">
            You may NOT scrape the site programmatically at a rate
            exceeding one request per second per IP, rehost the data as
            your own product, or use automated systems to submit the
            site&apos;s output as evidence in formal legal, regulatory,
            or intelligence-reporting contexts without independent
            verification.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3">
            5. Liability limit
          </h2>
          <p className="text-text-body leading-relaxed">
            To the maximum extent permitted by law, Atlas Peak Media, LLC
            will not be liable for any direct, indirect, incidental,
            special, consequential, or punitive damages arising out of
            your use of or inability to use the site, or from any
            analytical, editorial, operational, or policy decision you
            make on top of its data. Your sole remedy for dissatisfaction
            with the site is to stop using it.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3">
            6. Changes
          </h2>
          <p className="text-text-body leading-relaxed">
            We may update these terms at any time. Material changes will
            be reflected in the version number at the bottom of this
            page. Continued use of the site after an update constitutes
            acceptance of the updated terms. If you disagree with a
            change, stop using the site.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3">
            7. Governing law
          </h2>
          <p className="text-text-body leading-relaxed">
            These terms are governed by the laws of the State of Virginia,
            United States, without regard to conflict-of-law principles.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3">
            8. Contact
          </h2>
          <p className="text-text-body leading-relaxed">
            Questions, complaints, takedown requests, or disputes:{" "}
            <span className="text-mono">hello@atlaspeakmedia.com</span>.
            We read every message and respond when appropriate.
          </p>
        </section>

        <div className="border-t border-bg-divider pt-8 mt-12 text-sm text-text-secondary">
          <p>Version 1.0 / April 2026.</p>
        </div>
      </article>

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
