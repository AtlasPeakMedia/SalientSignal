"use client";

import { useEffect, useState } from "react";

interface Props {
  /**
   * ISO 639 locale tag for formatting. Defaults to "en-US".
   */
  locale?: string;
  /**
   * Intl.DateTimeFormatOptions subset. Defaults to HH:MM (24h off, en-US).
   */
  options?: Intl.DateTimeFormatOptions;
  /**
   * Extra classes for the wrapping span.
   */
  className?: string;
}

const DEFAULT_OPTIONS: Intl.DateTimeFormatOptions = {
  hour: "2-digit",
  minute: "2-digit",
};

/**
 * Clock — renders the current wall-clock time client-side only.
 *
 * B7 Firefox fix: previously the footer rendered
 *   {new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}
 * directly inside HomePageClient.tsx. Because the page is a server component
 * that hydrates on the client, React ran this Date() call on both the server
 * (at SSR time) and the client (at hydration time). The two clocks differed
 * by seconds-to-minutes, React logged a hydration mismatch warning + error,
 * and Firefox surfaced that as 2 console errors that broke client-side JS
 * execution for the route.
 *
 * This component isolates the wall-clock read into a "use client" boundary
 * with a ``useEffect`` that runs ONLY after hydration. The initial render
 * (both SSR and first client paint) shows an empty placeholder so the
 * server-rendered HTML matches the client's first paint exactly. The clock
 * label fills in on the very next render tick.
 *
 * No ticking interval — the clock updates once on mount. That's sufficient
 * for the "last rendered at" footer indicator and avoids a useless timer
 * running forever.
 */
export default function Clock({
  locale = "en-US",
  options = DEFAULT_OPTIONS,
  className,
}: Props) {
  const [label, setLabel] = useState("");

  useEffect(() => {
    // Delayed to useEffect so it runs ONLY on the client, post-hydration.
    try {
      setLabel(new Date().toLocaleTimeString(locale, options));
    } catch {
      // Some locales / options combinations can throw on older browsers.
      // Fall back to a stable ISO timestamp.
      setLabel(new Date().toISOString().slice(11, 16));
    }
    // Intentionally empty deps — we only render once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Empty placeholder on SSR and first client paint — matches the server
  // output deterministically, so hydration never logs a mismatch.
  return <span className={className}>{label}</span>;
}
