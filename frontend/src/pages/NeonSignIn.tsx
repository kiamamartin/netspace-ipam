/**
 * Neon Auth (Managed Better Auth) sign-in.
 *
 * Flow: the browser signs in against the managed Auth server, the session JWT
 * is exchanged at POST /api/v1/auth/neon/session for the app's own bearer
 * session (provisioning a local user on first use), and the shell opens.
 * v1 username/password login remains available from the operator sign-in page.
 */
import { type FormEvent, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { errorMessage, api } from '../api'
import { setSession, type AuthUser } from '../auth'
import { getNeonAuthClient, neonAuthBaseUrl, neonAuthConfigured } from '../neonAuth'
import { Icon } from '../ui'

/**
 * Fetch the session JWT from the managed Auth server. @neon/auth 0.8.2 does
 * not expose a typed `token()` method, so call the documented `/token` route
 * directly; the session cookie is sent with the credentialed request.
 */
async function requestJwt(): Promise<string> {
  const res = await fetch(`${neonAuthBaseUrl.replace(/\/$/, '')}/token`, { credentials: 'include' })
  const body = (await res.json().catch(() => null)) as { token?: string } | null
  if (!res.ok || !body?.token) {
    throw new Error(`Could not obtain a JWT from Neon Auth (HTTP ${res.status})`)
  }
  return body.token
}

export default function NeonSignIn() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  /** Verify with Neon, trade the identity for an app session, enter the shell. */
  const enterApp = async () => {
    setBusy(true)
    setError(null)
    try {
      const jwt = await requestJwt()
      const res = await fetch('/api/v1/auth/neon/session', {
        method: 'POST',
        headers: { Authorization: `Bearer ${jwt}` },
      })
      const body = (await res.json().catch(() => null)) as
        | { access_token: string; username: string; role: string }
        | { error?: { message?: string } }
        | null
      if (!res.ok || !body || !('access_token' in body)) {
        const message = body && 'error' in body ? body.error?.message : undefined
        throw new Error(message ?? `Could not create an app session (HTTP ${res.status})`)
      }
      setSession(body.access_token, {
        id: 0,
        username: body.username,
        role: body.role,
        is_active: true,
      } satisfies AuthUser)
      // Resolve the authoritative identity through the normal guard.
      const me = await api.get<AuthUser>('/api/v1/auth/me')
      setSession(body.access_token, me)
      navigate('/', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  // Session restoration: a live Neon session enters the app directly.
  const restored = useRef(false)
  useEffect(() => {
    if (!neonAuthConfigured || restored.current) return
    let alive = true
    getNeonAuthClient()
      .getSession()
      .then(({ data }) => {
        if (alive && data?.user) {
          restored.current = true
          void enterApp()
        }
      })
      .catch(() => {
        /* no session — stay on the form */
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const client = getNeonAuthClient()
      const result =
        mode === 'signup'
          ? await client.signUp.email({ email, password, name: name || email.split('@')[0] })
          : await client.signIn.email({ email, password })
      if (result.error) {
        setError(result.error.message ?? 'Neon Auth request failed')
        setBusy(false)
        return
      }
      await enterApp()
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="brand">
          <span className="brand-mark">
            <Icon name="network" size={16} />
          </span>
          NetSpace <small>IPAM</small>
        </div>
        <p className="login-sub">Sign in with Neon Auth to enter the application.</p>

        {!neonAuthConfigured && (
          <div className="login-error">
            Neon Auth is not configured. Set VITE_NEON_AUTH_URL in frontend/.env.local.
          </div>
        )}

        <form className="form-grid" onSubmit={submit}>
          {mode === 'signup' && (
            <label className="field">
              <span>Name</span>
              <input name="name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
            </label>
          )}
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              name="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              name="password"
              autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
            />
          </label>
          {error && <div className="login-error">{error}</div>}
          <div className="form-actions">
            <button className="btn primary" type="submit" disabled={busy || !email || !password}>
              <Icon name="power" size={13} />{' '}
              {busy ? 'Signing in…' : mode === 'signup' ? 'Create account' : 'Sign in with Neon'}
            </button>
            <button
              className="btn subtle"
              type="button"
              onClick={() => setMode(mode === 'signin' ? 'signup' : 'signin')}
              disabled={busy}
            >
              {mode === 'signin' ? 'Create account' : 'Have an account?'}
            </button>
          </div>
        </form>

        <p className="login-sub" style={{ marginTop: 18 }}>
          <Link to="/">← Back to operator sign-in</Link>
        </p>
      </div>
    </div>
  )
}
