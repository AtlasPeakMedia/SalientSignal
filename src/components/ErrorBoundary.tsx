"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** Optional fallback UI. If not provided, a default error panel is rendered. */
  fallback?: ReactNode;
  /** Optional label for the error panel (e.g. "Globe", "Country page"). */
  label?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * ErrorBoundary — React class component that catches client-side render
 * errors in its children and renders a fallback instead of crashing the
 * whole page.
 *
 * Why we need this: the Firefox /country/CN hydration mismatch (Phase B7)
 * was invisible to Chrome during local dev and only surfaced in Firefox
 * production, where it broke the entire page because there was no error
 * boundary to catch it. Wrapping the globe and country page content in
 * ErrorBoundary means a future bug of that class will render a small
 * "something went wrong" panel instead of a blank screen, and the user
 * can still navigate the rest of the site.
 *
 * React requires this to be a class component — hooks don't have an
 * equivalent yet (as of React 19). ``use client`` is needed because
 * componentDidCatch runs in the browser.
 *
 * Usage:
 *
 *   <ErrorBoundary label="Globe">
 *     <GlobeWrapper {...} />
 *   </ErrorBoundary>
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Surface to browser console for dev visibility. In production this
    // would ideally go to Sentry or similar, but we don't have an error
    // reporter wired up yet.
    // eslint-disable-next-line no-console
    console.error(
      `[ErrorBoundary${this.props.label ? ` ${this.props.label}` : ""}]`,
      error,
      errorInfo,
    );
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div
          role="alert"
          className="max-w-[1400px] mx-auto px-6 py-12 text-center"
        >
          <div className="inline-block px-6 py-5 rounded-md border border-bg-divider bg-bg-card">
            <div className="text-sm text-text-secondary uppercase tracking-wider mb-2">
              {this.props.label
                ? `${this.props.label} failed to render`
                : "Something went wrong"}
            </div>
            <div className="text-xs text-text-secondary font-mono max-w-md">
              {this.state.error?.message ?? "Unknown error"}
            </div>
            <button
              type="button"
              onClick={() => this.setState({ hasError: false, error: null })}
              className="mt-4 text-xs text-accent-tealBright hover:text-accent-tealMax transition-colors"
            >
              Try again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
