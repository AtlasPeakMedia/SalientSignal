"use client";

import { useEffect } from "react";
import type { CoordinationArc } from "@/lib/types";

interface Props {
  arc: CoordinationArc | null;
  onClose: () => void;
}

/**
 * ArcModal — opens when a coordination arc is clicked on the globe.
 *
 * Shows:
 *   - Theme label and score
 *   - Both country names with flag emojis
 *   - Confidence bar derived from the score
 *   - A short plain-English explanation of what the arc represents
 *   - "Close" button and click-outside-to-close
 *
 * This is intentionally a low-information modal. Coordination detection
 * in the MVP is crude (see /methodology section 6), so the modal has to
 * be honest about what it's claiming. It describes the observation, not
 * the interpretation.
 */
export default function ArcModal({ arc, onClose }: Props) {
  // Close on Escape
  useEffect(() => {
    if (!arc) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [arc, onClose]);

  if (!arc) return null;

  const scorePct = Math.round(arc.score * 100);
  const scoreLabel =
    arc.score >= 0.7
      ? "Strong"
      : arc.score >= 0.5
        ? "Moderate"
        : "Low";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="arc-modal-title"
      className="fixed inset-0 z-40 flex items-center justify-center p-4"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
      />

      {/* Panel */}
      <div
        className="relative w-full max-w-lg rounded-lg border border-bg-divider bg-bg-card shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-5 border-b border-bg-divider flex items-start justify-between">
          <div>
            <div className="text-xs text-accent-tealBright uppercase tracking-wider mb-1">
              Coordination Arc
            </div>
            <h2
              id="arc-modal-title"
              className="text-lg font-semibold text-white"
            >
              {arc.themeLabel}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-text-secondary hover:text-text-body transition-colors"
          >
            <svg
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="h-4 w-4"
            >
              <path
                d="M3 3l10 10M13 3L3 13"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>

        <div className="px-6 py-5 space-y-5">
          {/* Country pair */}
          <div className="flex items-center justify-between">
            <div className="flex-1 text-left">
              <div className="text-xs text-text-secondary uppercase tracking-wider mb-1">
                From
              </div>
              <div className="text-base font-semibold text-text-body">
                {arc.startCountry}
              </div>
            </div>
            <div className="mx-4 text-accent-tealBright">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                className="h-5 w-5"
                aria-hidden="true"
              >
                <path
                  d="M3 12h18M14 5l7 7-7 7"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <div className="flex-1 text-right">
              <div className="text-xs text-text-secondary uppercase tracking-wider mb-1">
                To
              </div>
              <div className="text-base font-semibold text-text-body">
                {arc.endCountry}
              </div>
            </div>
          </div>

          {/* Score bar */}
          <div>
            <div className="flex items-center justify-between text-xs mb-1.5">
              <span className="text-text-secondary uppercase tracking-wider">
                Coordination confidence
              </span>
              <span className="text-mono text-text-body">
                {scoreLabel} ({scorePct}%)
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-bg-raised overflow-hidden">
              <div
                className="h-full rounded-full bg-accent-tealBright"
                style={{ width: `${scorePct}%` }}
              />
            </div>
          </div>

          {/* Explanation */}
          <div className="text-sm text-text-body leading-relaxed pt-2 border-t border-bg-divider">
            <p className="mb-3">
              Both {arc.startCountry} and {arc.endCountry} state media
              simultaneously spiked coverage of the{" "}
              <span className="text-white font-medium">{arc.themeLabel}</span>{" "}
              theme within a 24-hour window.
            </p>
            <p className="text-xs text-text-secondary leading-relaxed italic">
              This is correlation, not causation. A shared anniversary, a
              major world event, or wire service syndication can produce the
              same pattern. See the{" "}
              <a
                href="/methodology#6-coordination-detection"
                className="text-accent-tealBright hover:text-accent-tealMax transition-colors"
              >
                methodology page
              </a>{" "}
              section 6 for how this is computed and what the confidence
              score actually means.
            </p>
          </div>

          {/* Country pages */}
          <div className="flex gap-2 pt-2">
            <a
              href={`/country/${arc.startIso}`}
              className="flex-1 text-center px-4 py-2 text-xs font-medium rounded-full bg-bg-raised text-text-body hover:bg-accent-teal hover:text-white transition-colors"
            >
              View {arc.startCountry} →
            </a>
            <a
              href={`/country/${arc.endIso}`}
              className="flex-1 text-center px-4 py-2 text-xs font-medium rounded-full bg-bg-raised text-text-body hover:bg-accent-teal hover:text-white transition-colors"
            >
              View {arc.endCountry} →
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
