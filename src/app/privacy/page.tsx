import Link from "next/link";
import type { Metadata } from "next";
import Wordmark from "@/components/Brand/Wordmark";
import { requireAuth } from "@/lib/auth";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export const metadata: Metadata = {
  title: "Privacy — SalientSignal",
  description:
    "What SalientSignal does and does not collect. Short version: we don't track you.",
};

export default async function PrivacyPage() {
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
              PRIVACY
            </span>
          </nav>
        </div>
      </header>

      <article className="max-w-3xl mx-auto px-6 py-16">
        <h1 className="text-4xl font-bold text-white mb-2 tracking-tight">
          Privacy
        </h1>
        <p className="text-sm text-text-secondary mb-10">
          Short version: we don&apos;t track you, we don&apos;t sell data about
          you, and we don&apos;t have user accounts for you to lose data from.
        </p>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3">
            What we collect
          </h2>
          <p className="text-text-body leading-relaxed mb-4">
            SalientSignal is a read-only intelligence product. There are no
            accounts, no login (beyond the pre-launch password gate, which
            uses a short-lived HttpOnly cookie), and no user-generated
            content. The only data we collect on visitors is whatever the
            underlying hosting stack logs by default:
          </p>
          <ul className="list-disc list-outside pl-6 space-y-2 text-text-body">
            <li>
              <strong className="text-white">Vercel</strong>, our hosting
              provider, retains anonymous request logs (IP address,
              timestamp, path, user agent, referrer) for standard
              operational purposes. We do not ingest or process these logs
              ourselves. See{" "}
              <a
                href="https://vercel.com/legal/privacy-policy"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent-tealBright hover:text-accent-tealMax"
              >
                Vercel&apos;s privacy policy
              </a>{" "}
              for retention and jurisdiction details.
            </li>
            <li>
              <strong className="text-white">Supabase</strong>, our database
              provider, retains query-side metadata similarly. Our
              application code only issues SELECT queries from the public
              route code — no visitor data is written to the database.
            </li>
          </ul>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3">
            What we DO NOT collect
          </h2>
          <ul className="list-disc list-outside pl-6 space-y-2 text-text-body">
            <li>
              No advertising tracking, no third-party analytics, no Google
              Analytics, no Meta Pixel, no marketing cookies
            </li>
            <li>
              No email addresses, no usernames, no passwords (the pre-launch
              gate uses a shared password, not a per-user credential)
            </li>
            <li>No payment information (the MVP is free to use)</li>
            <li>No location tracking</li>
            <li>No cross-site tracking</li>
            <li>
              No aggregation of visitor behavior for resale or profiling
            </li>
          </ul>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3">
            Cookies
          </h2>
          <p className="text-text-body leading-relaxed">
            We set exactly one cookie: <span className="text-mono">ss_auth</span>,
            the pre-launch password gate. It is HttpOnly, Secure, SameSite-Lax,
            and expires 30 days after it&apos;s set. When the site goes public
            after JAG review, this cookie will be removed entirely and no
            cookies will be used.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3">
            What SalientSignal publishes about others
          </h2>
          <p className="text-text-body leading-relaxed mb-4">
            The data we display is about public state-media outlets and
            their publication patterns — not about individual readers,
            journalists, or private citizens. The source material comes
            from the publicly-available{" "}
            <a
              href="https://www.gdeltproject.org/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-tealBright hover:text-accent-tealMax"
            >
              GDELT Project
            </a>
            , which monitors news outlet RSS feeds and web archives with
            permission. SalientSignal aggregates daily publication volume
            and never republishes full article text.
          </p>
          <p className="text-text-body leading-relaxed">
            If an outlet classification is incorrect (wrong country, wrong
            audience type, wrong state-ownership status), email{" "}
            <span className="text-mono">hello@atlaspeakmedia.com</span> and
            we will investigate. Corrections are free and typically
            processed within a few days.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3">
            Data requests
          </h2>
          <p className="text-text-body leading-relaxed">
            Because we don&apos;t maintain user accounts or behavioral
            profiles, standard GDPR/CCPA data-subject requests for "what
            do you have on me" return an empty set by design. If you
            believe we have retained data about you through some
            infrastructure-level logging, contact{" "}
            <span className="text-mono">hello@atlaspeakmedia.com</span> and
            we will help you direct the request to Vercel or Supabase as
            appropriate.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="text-xl font-semibold text-white mb-3">
            Changes to this policy
          </h2>
          <p className="text-text-body leading-relaxed">
            When paid tiers launch post-MVP, this policy will be updated
            to cover payment processing (handled by Stripe, not us) and
            the short-lived customer records needed for subscription
            management. Core "we don&apos;t track you" principles will not
            change.
          </p>
        </section>

        <div className="border-t border-bg-divider pt-8 mt-12 text-sm text-text-secondary">
          <p>
            Questions: <span className="text-mono">hello@atlaspeakmedia.com</span>.
            Version 1.0 / April 2026.
          </p>
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
