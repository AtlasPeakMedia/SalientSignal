/**
 * Edge middleware — password gate for pre-launch access control.
 *
 * Runs before every request. If the requester has a valid `ss_auth` cookie,
 * the request is allowed through. Otherwise, they're redirected to /login.
 *
 * This is intentionally simple: one shared password, one long-lived cookie.
 * Same pattern as donsflashcards.com. Not meant to resist a determined
 * attacker — just keeps the site out of search engines and away from casual
 * visitors until JAG/ethics review is complete.
 *
 * Environment variables required in Vercel:
 *   SITE_PASSWORD     — the shared password users type on /login
 *   SITE_AUTH_SECRET  — random 32+ char string used as the cookie value
 *
 * To rotate access: change SITE_AUTH_SECRET in Vercel and every existing
 * cookie becomes invalid. SITE_PASSWORD can be changed independently.
 */
import { NextResponse, type NextRequest } from "next/server";

const AUTH_COOKIE = "ss_auth";
const LOGIN_PATH = "/login";

// Paths the middleware will NOT gate. Everything else requires the cookie.
const PUBLIC_PREFIXES = [
  LOGIN_PATH,
  "/_next",
  "/favicon.ico",
  "/robots.txt",
  "/data/", // the geojson file lives here
];

// Response headers applied to every authenticated page load.
// noindex + nofollow ensures search engines won't index the site even
// if the robots.txt is ignored.
function applySecurityHeaders(response: NextResponse): NextResponse {
  response.headers.set("X-Robots-Tag", "noindex, nofollow, noarchive, nosnippet");
  response.headers.set("Referrer-Policy", "no-referrer");
  return response;
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths straight through.
  if (PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix))) {
    return applySecurityHeaders(NextResponse.next());
  }

  // Check the auth cookie.
  const cookie = request.cookies.get(AUTH_COOKIE);
  const expected = process.env.SITE_AUTH_SECRET;

  if (cookie?.value && expected && cookie.value === expected) {
    // Valid cookie — allow through with security headers.
    return applySecurityHeaders(NextResponse.next());
  }

  // No cookie (or wrong value) — redirect to the login page.
  // Preserve the original path so we can bounce them back after auth.
  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = LOGIN_PATH;
  loginUrl.searchParams.set("from", pathname);
  return applySecurityHeaders(NextResponse.redirect(loginUrl));
}

// Matcher: run on everything except Next.js internals and static files.
// We can't use PUBLIC_PREFIXES directly here because `matcher` must be a
// compile-time constant. The `middleware` function above does the runtime
// filtering.
export const config = {
  matcher: [
    "/((?!_next/static|_next/image|_next/data|favicon\\.ico|robots\\.txt).*)",
  ],
};
