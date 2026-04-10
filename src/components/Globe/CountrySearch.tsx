"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { CountryActivity } from "@/lib/types";

interface Props {
  /**
   * All monitored countries (unfiltered — we want search to find countries
   * even when the region filter is active, so users can jump to Belarus
   * from the Eastern Europe view).
   */
  countries: CountryActivity[];
}

/**
 * Country search combobox. Click to expand, type to filter by name or ISO
 * code, Enter to navigate to the selected country page.
 *
 * Why this exists: tiny island nations and small countries are hard to tap
 * on the globe. Power users also want to jump to a country by typing its
 * name rather than panning/zooming. This gives both audiences a keyboard-
 * first path without cluttering the main UI.
 *
 * UX:
 *   - Closed state: small button that says "Search..."
 *   - Open state: input field with dropdown of matching countries
 *   - Arrow up/down to navigate, Enter to select, Escape to close
 *   - Click outside to close
 *   - Shows flag + name + ISO code per result
 */
export default function CountrySearch({ countries }: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Sort once and cache — countries list is stable per render.
  const sorted = useMemo(
    () => [...countries].sort((a, b) => a.name.localeCompare(b.name)),
    [countries],
  );

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return sorted.slice(0, 50);
    return sorted.filter(
      (c) =>
        c.name.toLowerCase().includes(q) || c.iso2.toLowerCase().includes(q),
    );
  }, [sorted, query]);

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

  // Focus the input when opening
  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
      setActiveIndex(0);
    }
  }, [open]);

  // Reset activeIndex when results shrink past it
  useEffect(() => {
    if (activeIndex >= results.length && results.length > 0) {
      setActiveIndex(0);
    }
  }, [results.length, activeIndex]);

  const navigate = (iso2: string) => {
    setOpen(false);
    setQuery("");
    router.push(`/country/${iso2}`);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, results.length - 1));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      const pick = results[activeIndex];
      if (pick) navigate(pick.iso2);
      return;
    }
  };

  return (
    <div ref={containerRef} className="relative inline-block">
      {!open ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Search countries"
          className="inline-flex items-center gap-2 px-4 py-1.5 text-xs font-medium rounded-full border border-bg-divider bg-bg-card text-text-secondary hover:text-text-body transition-colors"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="h-3.5 w-3.5"
          >
            <circle cx="7" cy="7" r="5" />
            <path d="M13.5 13.5l-2.5-2.5" strokeLinecap="round" />
          </svg>
          <span>Search</span>
        </button>
      ) : (
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-accent-teal bg-bg-card">
          <svg
            aria-hidden="true"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="h-3.5 w-3.5 text-text-secondary"
          >
            <circle cx="7" cy="7" r="5" />
            <path d="M13.5 13.5l-2.5-2.5" strokeLinecap="round" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search countries..."
            className="bg-transparent border-none outline-none text-xs text-text-body placeholder:text-text-secondary w-44"
            aria-label="Country name or ISO code"
            role="combobox"
            aria-expanded="true"
            aria-controls="country-search-results"
          />
        </div>
      )}

      {open && (
        <ul
          id="country-search-results"
          role="listbox"
          className="absolute right-0 mt-2 w-72 max-h-80 overflow-y-auto rounded-md border border-bg-divider bg-bg-card shadow-lg z-20"
        >
          {results.length === 0 ? (
            <li className="px-3 py-3 text-xs text-text-secondary italic">
              No countries match "{query}"
            </li>
          ) : (
            results.map((c, idx) => (
              <li key={c.iso2} role="option" aria-selected={idx === activeIndex}>
                <button
                  type="button"
                  onMouseEnter={() => setActiveIndex(idx)}
                  onClick={() => navigate(c.iso2)}
                  className={`w-full flex items-center gap-3 px-3 py-2 text-xs text-left transition-colors ${
                    idx === activeIndex
                      ? "bg-bg-raised/80"
                      : "hover:bg-bg-raised/60"
                  }`}
                >
                  <span className="text-base leading-none">{c.flag}</span>
                  <span className="flex-1 text-text-body">{c.name}</span>
                  <span className="text-mono text-text-secondary">
                    {c.iso2}
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
