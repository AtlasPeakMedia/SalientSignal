"use client";

import { useEffect, useRef, useState } from "react";
import { REGIONS, type Region } from "@/lib/country-regions";

interface Props {
  /** Currently selected regions. ``null`` means "all regions" (no filter). */
  selected: Set<Region> | null;
  /** Callback invoked with the new selected set. ``null`` means "reset to all". */
  onChange: (next: Set<Region> | null) => void;
}

/**
 * Collapsible multi-select region filter for the globe.
 *
 * Behavior:
 *   - Default state (selected=null) = "All regions", no filter applied
 *   - Click the button to open/close the dropdown
 *   - Click a region checkbox to toggle it; the filter immediately flips
 *     from "all" mode to explicit-set mode
 *   - Click "Reset" at the top of the dropdown to go back to "all"
 *   - Click outside the dropdown to close it
 *
 * Visual layout matches ViewToggle (rounded-full pill, same palette) so the
 * controls row reads as a coherent set.
 */
export default function RegionFilter({ selected, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const toggleRegion = (region: Region) => {
    const base = selected ?? new Set<Region>(REGIONS.map((r) => r.value));
    const next = new Set(base);
    if (next.has(region)) {
      next.delete(region);
    } else {
      next.add(region);
    }
    // If every region is selected, collapse back to null ("all regions")
    if (next.size === REGIONS.length) {
      onChange(null);
    } else {
      onChange(next);
    }
  };

  const selectAll = () => onChange(null);
  const deselectAll = () => onChange(new Set<Region>());

  const label = (() => {
    if (selected === null) return "All regions";
    if (selected.size === 0) return "No regions";
    if (selected.size === 1) {
      const only = Array.from(selected)[0];
      return REGIONS.find((r) => r.value === only)?.label ?? "1 region";
    }
    return `${selected.size} regions`;
  })();

  return (
    <div ref={containerRef} className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={`inline-flex items-center gap-2 px-4 py-1.5 text-xs font-medium rounded-full border transition-colors ${
          selected !== null && selected.size < REGIONS.length
            ? "border-accent-teal bg-accent-teal/10 text-text-body"
            : "border-bg-divider bg-bg-card text-text-secondary hover:text-text-body"
        }`}
      >
        <span>Region: {label}</span>
        <svg
          aria-hidden="true"
          className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`}
          viewBox="0 0 12 12"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path d="M3 4.5l3 3 3-3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div
          role="listbox"
          aria-label="Filter globe by region"
          className="absolute right-0 mt-2 w-64 max-h-[70vh] overflow-y-auto rounded-md border border-bg-divider bg-bg-card shadow-lg z-20"
        >
          <div className="px-3 py-2 border-b border-bg-divider">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[11px] uppercase tracking-wider text-text-secondary">
                Filter regions
              </span>
              <span className="text-[11px] text-mono text-text-secondary">
                {selected === null
                  ? REGIONS.length
                  : selected.size}
                /{REGIONS.length}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={selectAll}
                disabled={selected === null}
                className="text-[11px] text-accent-tealBright hover:text-accent-tealMax transition-colors disabled:text-text-secondary disabled:cursor-not-allowed"
              >
                Select all
              </button>
              <span className="text-[11px] text-bg-divider" aria-hidden="true">
                ·
              </span>
              <button
                type="button"
                onClick={deselectAll}
                disabled={selected !== null && selected.size === 0}
                className="text-[11px] text-accent-tealBright hover:text-accent-tealMax transition-colors disabled:text-text-secondary disabled:cursor-not-allowed"
              >
                Deselect all
              </button>
            </div>
          </div>
          <ul className="py-1">
            {REGIONS.map((r) => {
              // If selected is null, every region is effectively "on"
              const isOn = selected === null || selected.has(r.value);
              return (
                <li key={r.value}>
                  <button
                    type="button"
                    onClick={() => toggleRegion(r.value)}
                    className="w-full flex items-center gap-3 px-3 py-2 text-xs text-left hover:bg-bg-raised/60 transition-colors"
                    role="option"
                    aria-selected={isOn}
                  >
                    <span
                      aria-hidden="true"
                      className={`flex h-4 w-4 items-center justify-center rounded border ${
                        isOn
                          ? "border-accent-teal bg-accent-teal text-white"
                          : "border-bg-divider"
                      }`}
                    >
                      {isOn && (
                        <svg
                          viewBox="0 0 12 12"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          className="h-3 w-3"
                        >
                          <path
                            d="M2.5 6.5l2.5 2.5 4.5-5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      )}
                    </span>
                    <span
                      className={
                        isOn ? "text-text-body" : "text-text-secondary"
                      }
                    >
                      {r.label}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
