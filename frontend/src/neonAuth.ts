/**
 * Neon Auth (Managed Better Auth) browser client.
 *
 * The auth server is hosted by Neon; this app only holds the public branch URL
 * (VITE_NEON_AUTH_URL — `neon env pull` does not create this Vite alias, so it
 * is set in frontend/.env.local). Never place the Better Auth secret here.
 */
import { createAuthClient } from '@neon/auth'
import { BetterAuthReactAdapter } from '@neon/auth/react/adapters'

const baseUrl = import.meta.env.VITE_NEON_AUTH_URL as string | undefined

export const neonAuthConfigured = Boolean(baseUrl)
/** Public managed Auth base URL (safe to expose; contains no secrets). */
export const neonAuthBaseUrl = baseUrl ?? ''

function makeClient() {
  // The overload with the React adapter resolves to the Better Auth client
  // type (signIn/signUp/token/getSession), not the adapter union.
  return createAuthClient(baseUrl ?? '', { adapter: BetterAuthReactAdapter() })
}

type NeonAuthClient = ReturnType<typeof makeClient>

let client: NeonAuthClient | null = null

/** Lazily create the client so a missing env var degrades the page, not the app. */
export function getNeonAuthClient(): NeonAuthClient {
  if (!baseUrl) {
    throw new Error('Neon Auth is not configured: set VITE_NEON_AUTH_URL in frontend/.env.local')
  }
  client ??= makeClient()
  return client
}
