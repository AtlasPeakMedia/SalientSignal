import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import Wordmark from "@/components/Brand/Wordmark";

// Login must never be prerendered — it needs fresh env vars and cookies
// on every request.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const AUTH_COOKIE = "ss_auth";

interface PageProps {
  searchParams: Promise<{ error?: string; from?: string }>;
}

async function loginAction(formData: FormData) {
  "use server";

  const password = String(formData.get("password") ?? "");
  const from = String(formData.get("from") ?? "/");

  const expected = process.env.SITE_PASSWORD;
  const secret = process.env.SITE_AUTH_SECRET;

  if (!expected || !secret) {
    // Misconfigured — fail closed with a generic error so we don't leak
    // which env var is missing.
    redirect("/login?error=config");
  }

  if (password !== expected) {
    redirect("/login?error=wrong");
  }

  // Success: set a 30-day cookie with the server secret as the value.
  // Rotating SITE_AUTH_SECRET invalidates all existing cookies instantly.
  const cookieStore = await cookies();
  cookieStore.set(AUTH_COOKIE, secret, {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 30, // 30 days
  });

  // Bounce back to wherever they were trying to go. Default to /.
  // Strip anything that looks like a protocol to prevent open redirect.
  const safeFrom =
    from.startsWith("/") && !from.startsWith("//") ? from : "/";
  redirect(safeFrom);
}

export default async function LoginPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const errorMessage =
    params.error === "wrong"
      ? "Incorrect password."
      : params.error === "config"
        ? "Site is not configured. Contact the administrator."
        : null;

  return (
    <main className="min-h-screen flex items-center justify-center px-6">
      <div className="max-w-sm w-full">
        <div className="mb-8 text-center">
          <Wordmark />
        </div>

        <div className="card p-8">
          <h1 className="text-lg font-semibold text-white mb-1">
            Access restricted
          </h1>
          <p className="text-xs text-text-secondary mb-6">
            SalientSignal is pre-launch. Enter the access password to continue.
          </p>

          <form action={loginAction} className="space-y-4">
            <input type="hidden" name="from" value={params.from ?? "/"} />
            <div>
              <label
                htmlFor="password"
                className="block text-xs uppercase tracking-wider text-text-secondary mb-2"
              >
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                autoFocus
                required
                className="w-full px-4 py-3 bg-bg-base border border-bg-divider rounded-md text-white text-sm focus:outline-none focus:border-accent-teal transition-colors"
              />
            </div>

            {errorMessage && (
              <div className="text-xs text-red-400" role="alert">
                {errorMessage}
              </div>
            )}

            <button
              type="submit"
              className="w-full px-4 py-3 bg-accent-teal hover:bg-accent-tealBright text-white text-sm font-medium rounded-md transition-colors"
            >
              Enter
            </button>
          </form>
        </div>

        <p className="text-xs text-text-secondary text-center mt-6">
          Atlas Peak Media, LLC
        </p>
      </div>
    </main>
  );
}
