"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "salientsignal.tutorial.dismissed";

const STEPS = [
  {
    title: "Tap any country",
    body: "Click a country on the globe to see what its state media is publishing today.",
  },
  {
    title: "Domestic vs. International",
    body: "Use the view toggle to compare what regimes tell their own citizens versus what they tell foreign audiences. This split is the core of the product.",
  },
  {
    title: "Filter by region",
    body: "Use the Region dropdown to narrow the globe to one part of the world — Middle East, East Asia, Sub-Saharan Africa, etc.",
  },
  {
    title: "Arcs show coordination",
    body: "Glowing arcs between countries indicate shared theme spikes within 24 hours. Click an arc to see details and the full coordination score.",
  },
];

/**
 * InlineTutorial — first-visit dismissible overlay.
 *
 * Shows a 4-step carousel over the globe on the first visit of each
 * browser session, then sets a localStorage flag so it never re-appears.
 * Low-friction: no modal backdrop, no blocking. It sits in a corner and
 * waits for the user to dismiss it or reach the last step.
 *
 * Why it exists: the product's core innovation (domestic vs. international
 * audience split + baseline deviation on a globe) is novel enough that
 * first-time visitors need a nudge. Without this, we've seen testers spend
 * 30+ seconds trying to figure out what the colors mean. The tutorial
 * pre-empts that confusion.
 *
 * Dismissal is permanent (per browser, per localStorage). No "show
 * tutorial again" button because once you know, you know.
 */
export default function InlineTutorial() {
  const [dismissed, setDismissed] = useState<boolean | null>(null);
  const [step, setStep] = useState(0);

  // Load dismissal state from localStorage. Null during the initial render
  // pass so SSR + first client paint match (empty output).
  useEffect(() => {
    try {
      setDismissed(window.localStorage.getItem(STORAGE_KEY) === "1");
    } catch {
      setDismissed(false);
    }
  }, []);

  const dismiss = () => {
    setDismissed(true);
    try {
      window.localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      // storage might be disabled (incognito with lockdown settings);
      // at worst the tutorial re-shows on next visit which is fine.
    }
  };

  const next = () => {
    if (step < STEPS.length - 1) {
      setStep((s) => s + 1);
    } else {
      dismiss();
    }
  };

  // Hide entirely on SSR + first paint, or when dismissed.
  if (dismissed !== false) return null;

  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;

  return (
    <div
      role="dialog"
      aria-label="First-visit tutorial"
      className="fixed bottom-6 right-6 z-30 w-80 rounded-lg border border-bg-divider bg-bg-card shadow-xl"
    >
      <div className="px-4 pt-3 pb-2 flex items-center justify-between border-b border-bg-divider">
        <span className="text-[11px] text-accent-tealBright uppercase tracking-wider font-medium">
          Step {step + 1} of {STEPS.length}
        </span>
        <button
          type="button"
          onClick={dismiss}
          aria-label="Dismiss tutorial"
          className="text-text-secondary hover:text-text-body transition-colors"
        >
          <svg
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="h-3.5 w-3.5"
          >
            <path d="M3 3l10 10M13 3L3 13" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      <div className="px-4 py-4">
        <h3 className="text-sm font-semibold text-white mb-1.5">
          {current.title}
        </h3>
        <p className="text-xs text-text-secondary leading-relaxed mb-4">
          {current.body}
        </p>

        <div className="flex items-center justify-between">
          <div className="flex gap-1.5" aria-hidden="true">
            {STEPS.map((_, i) => (
              <span
                key={i}
                className={`h-1.5 w-1.5 rounded-full transition-colors ${
                  i === step ? "bg-accent-tealBright" : "bg-bg-divider"
                }`}
              />
            ))}
          </div>
          <button
            type="button"
            onClick={next}
            className="text-xs font-medium text-accent-tealBright hover:text-accent-tealMax transition-colors"
          >
            {isLast ? "Got it" : "Next →"}
          </button>
        </div>
      </div>
    </div>
  );
}
