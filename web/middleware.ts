/**
 * Edge middleware — password gate for pre-launch access control.
 *
 * Runs before every request. If the requester has a valid `ss_auth` cookie,
 * the request passes through. Otherwise they're redirected to /login.
 *
 * Same shared-password pattern as donsflashcards.com. Not cryptographically
 * robust — just keeps the site out of search engines and away from casual
 * visitors until JAG/ethics review is complete.
 *
 * Environment variables:
 *   SITE_PASSWORD     — shared password users type on /login
 *   SITE_AUTH_SECRET  — value stored in the ss_auth cookie; rotate to invalidate
 *
 * Defensive: wraps the whole handler in try/catch and FAILS OPEN on any
 * unexpected error. That way a middleware bug never bricks the site — you
 * still see content (at worst, the site is publicly visible instead of
 * gated, which we catch with X-Robots-Tag and robots.txt anyway).
 */
import { NextResponse, type NextRequest } from "next/server";

const AUTH_COOKIE = "ss_auth";
const LOGIN_PATH = "/login";

export function middleware(request: NextRequest) {
  try {
    const pathname = request.nextUrl.pathname;

    // Public paths bypass the gate.
    if (
      pathname === "/login" ||
      pathname.startsWith("/login/") ||
      pathname.startsWith("/_next") ||
      pathname.startsWith("/data/") ||
      pathname === "/favicon.ico" ||
      pathname === "/robots.txt"
    ) {
      return NextResponse.next();
    }

    // Auth cookie check.
    const cookieValue = request.cookies.get(AUTH_COOKIE)?.value;
    const expected = process.env.SITE_AUTH_SECRET;

    if (cookieValue && expected && cookieValue === expected) {
      return NextResponse.next();
    }

    // No valid cookie — redirect to /login with original destination.
    // Use standard URL construction instead of nextUrl.clone() to minimize
    // surface area for runtime errors.
    const redirectUrl = new URL("/login", request.url);
    redirectUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(redirectUrl);
  } catch (err) {
    // Fail open: never let a middleware bug 500 the whole site. Log and
    // allow the request through. X-Robots-Tag headers in next.config.ts
    // + robots.txt still keep search engines out.
    console.error("[middleware] caught unexpected error, failing open:", err);
    return NextResponse.next();
  }
}

// Matcher: run on everything except Next.js static asset paths and the
// favicon/robots special files. Simpler pattern than before — no nested
// negative lookaheads, no backslash-escaped dots.
export const config = {
  matcher: ["/((?!_next|favicon.ico|robots.txt).*)"],
};
