/**
 * MINIMAL DIAGNOSTIC MIDDLEWARE — does nothing.
 *
 * Temporarily stripped down to the absolute minimum while we figure out
 * why MIDDLEWARE_INVOCATION_FAILED is firing. If this version still 500s,
 * the problem is in Vercel's middleware bundling/runtime on this project,
 * not in our middleware logic.
 *
 * Once we have a working baseline, the password gate logic from commit
 * 4b10d7b will be added back.
 */
import { NextResponse } from "next/server";

export function middleware() {
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next|favicon.ico|robots.txt).*)"],
};
