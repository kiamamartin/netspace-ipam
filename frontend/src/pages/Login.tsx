import { type FormEvent, useState } from 'react'
import { api, errorMessage } from '../api'
import { setSession, type AuthUser } from '../auth'
import { Icon } from '../ui'

/**
 * Login screen (M5 AAA). Posts to POST /api/v1/auth/login; the backend is the
 * single authority for credentials and roles. Seeded dev accounts:
 *   admin / operator / viewer (passwords distributed by the operator console).
 */
export default function Login({ onSignedIn }: { onSignedIn: (user: AuthUser) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const res = await api.post<{
        access_token: string
        username: string
        role: string
        expires_in_minutes: number
      }>('/api/v1/auth/login', { username, password })
      setSession(res.access_token, {
        id: 0,
        username: res.username,
        role: res.role,
        is_active: true,
      })
      // resolve the authoritative identity through /auth/me (token now auto-attached)
      const me = await api.get<{ id: number; username: string; role: string; is_active: boolean }>(
        '/api/v1/auth/me',
      )
      setSession(res.access_token, me)
      onSignedIn(me)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
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
        <p className="login-sub">Sign in with your network operator account.</p>
        <form className="form-grid" onSubmit={submit}>
          <label className="field">
            <span>Username</span>
            <input
              autoFocus
              name="username"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && <div className="login-error">{error}</div>}
          <div className="form-actions">
            <button className="btn primary" type="submit" disabled={busy || !username || !password}>
              <Icon name="power" size={13} /> {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
