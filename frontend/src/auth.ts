/**
 * Client-side session for NetSpace IPAM (M5 AAA).
 *
 * The backend issues HS256 bearer tokens via POST /api/v1/auth/login and
 * enforces role-based authorization server-side (viewer < operator < admin).
 * This module only keeps the resolved session in localStorage and exposes it
 * to the API client and the shell; it never makes authorization decisions.
 */

export interface AuthUser {
  id: number
  username: string
  role: 'viewer' | 'operator' | 'admin' | string
  is_active: boolean
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in_minutes: number
  username: string
  role: string
}

const TOKEN_KEY = 'netspace.token'
const USER_KEY = 'netspace.user'

type Listener = (user: AuthUser | null) => void
const listeners = new Set<Listener>()

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function getUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    if (!raw) return null
    const user = JSON.parse(raw) as AuthUser
    if (!user || typeof user.username !== 'string') return null
    return user
  } catch {
    return null
  }
}

export function setSession(token: string, user: AuthUser): void {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
  listeners.forEach((fn) => fn(user))
}

/** Invalidate the persisted session and notify subscribers. */
export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  listeners.forEach((fn) => fn(null))
}

/** Headers to attach bearer auth to a request (empty when signed out). */
export function authHeader(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function onAuthChange(fn: Listener): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
