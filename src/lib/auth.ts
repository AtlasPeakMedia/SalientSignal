/**
 * Server-side auth helper for the pre-launch password gate.
 *
 * Used by each page's server component instead of middleware. We tried
 * middleware.ts first but hit persistent MIDDLEWARE_INVOCATION_FAILED
 * errors on Vercel's edge runtime that we couldn't diagnose, so switched
 * to this per-page approach which runs on the Node.js runtime and has
 * none of the Edge Runtime restrictions.
 *
 * Usage (at the top of any page's server component):
 *
 *   import { requireAuth } from "@/lib/auth";
 *
 *   export default async function HomePage() {
 *     await requireAuth();
 *     // ... rest of page, only runs if user is authenticated
 *   }
 *
 * Environment variables:
 *   SITE_AUTH_SECRET — value stored in the ss_auth cookie. Set via the
 *                      /login server action after password validation.
 *                      Rotating this invalidates all existing sessions.
 */
import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export const AUTH_COOKIE = "ss_auth";
export const LOGIN_PATH = "/login";

/**
 * Require the caller to have a valid auth cookie. If not, redirect to
 * the login page. This THROWS a Next.js redirect error that bubbles
 * up to the framework, so it terminates page rendering. Callers don't
 * need to handle the return value — if the function returns normally,
 * the user is authenticated.
 */
export async function requireAuth(): Promise<void> {
  const cookieStore = await cookies();
  const cookieValue = cookieStore.get(AUTH_COOKIE)?.value;
  const expected = process.env.SITE_AUTH_SECRET;

  if (!cookieValue || !expected || cookieValue !== expected) {
    redirect(LOGIN_PATH);
  }
}

/**
 * Check auth without redirecting. Returns true if the user has a valid
 * cookie. Useful for conditional rendering rather than hard redirect.
 */
export async function isAuthenticated(): Promise<boolean> {
  const cookieStore = await cookies();
  const cookieValue = cookieStore.get(AUTH_COOKIE)?.value;
  const expected = process.env.SITE_AUTH_SECRET;
  return Boolean(cookieValue && expected && cookieValue === expected);
}
