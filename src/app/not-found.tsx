import Link from "next/link";
import Wordmark from "@/components/Brand/Wordmark";

export default function NotFound() {
  return (
    <main className="min-h-screen">
      <header className="border-b border-bg-divider">
        <div className="max-w-[1400px] mx-auto px-6 py-4">
          <Wordmark />
        </div>
      </header>

      <section className="max-w-3xl mx-auto px-6 py-24 text-center">
        <div className="text-sm text-text-secondary uppercase tracking-wider mb-4">
          404 · Not Found
        </div>
        <h1 className="text-4xl font-bold text-white mb-4">
          This signal is off the map.
        </h1>
        <p className="text-text-body leading-relaxed mb-10 max-w-xl mx-auto">
          The page you&apos;re looking for doesn&apos;t exist, or the country
          code you tried to visit isn&apos;t in our monitored set. We don&apos;t
          track Five Eyes media, so US, UK, Canadian, Australian, and New
          Zealand country pages are intentionally unavailable.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3 mb-12">
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-5 py-2 rounded-full bg-accent-teal text-white text-sm font-medium hover:bg-accent-tealBright transition-colors"
          >
            ← Back to the globe
          </Link>
          <Link
            href="/methodology"
            className="inline-flex items-center gap-2 px-5 py-2 rounded-full border border-bg-divider text-text-secondary text-sm hover:text-text-body transition-colors"
          >
            Methodology
          </Link>
        </div>

        <div className="pt-8 border-t border-bg-divider text-xs text-text-secondary">
          <p>
            Looking for a specific country? Try tapping it directly on the
            globe, or use the Region filter to narrow down a continent.
          </p>
        </div>
      </section>
    </main>
  );
}
