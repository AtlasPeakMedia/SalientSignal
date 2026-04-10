/**
 * Server-side Supabase client.
 *
 * Uses the service role key (SUPABASE_SECRET_KEY) — NEVER import this
 * from a client component. Only call from server components, API routes,
 * or `lib/data.ts` server helpers.
 *
 * We keep the key out of NEXT_PUBLIC_* vars deliberately: with RLS disabled
 * on every table (P2-C8), anyone with this key can read everything.
 */

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let cached: SupabaseClient | null = null;

/** Resolve the Supabase project URL from either env var convention. */
function resolveUrl(): string | undefined {
  return process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
}

/** Resolve the secret/service-role key — never exposed to the client. */
function resolveKey(): string | undefined {
  return process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY;
}

export function getServerSupabase(): SupabaseClient | null {
  if (cached) return cached;

  const url = resolveUrl();
  const key = resolveKey();
  if (!url || !key) return null;

  cached = createClient(url, key, {
    auth: {
      persistSession: false,
      autoRefreshToken: false,
    },
  });
  return cached;
}

export function hasSupabaseCredentials(): boolean {
  return Boolean(resolveUrl() && resolveKey());
}
