import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { getUser } from '../auth'
import { api, errorMessage, type UserAccount } from '../api'
import {
  ErrorBanner,
  Icon,
  Loading,
  Modal,
  PageHead,
  RowMenu,
  SelectField,
  TextField,
} from '../ui'
import { confirmAction, notify } from '../feedback'

const ROLES = ['viewer', 'operator', 'admin']

export default function Users() {
  const me = getUser()
  const [items, setItems] = useState<UserAccount[]>([])
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<UserAccount | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState({ username: '', password: '', role: 'viewer', is_active: true })

  const load = useCallback(() => {
    if (me?.role !== 'admin') return
    api
      .get<UserAccount[]>('/api/v1/auth/users')
      .then((users) => {
        setItems(users)
        setError(null)
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoaded(true))
  }, [me?.role])

  useEffect(() => {
    load()
  }, [load])

  function resetForm() {
    setEditing(null)
    setForm({ username: '', password: '', role: 'viewer', is_active: true })
    setShowForm(false)
  }

  function startCreate() {
    resetForm()
    setShowForm(true)
  }

  function startEdit(user: UserAccount) {
    setEditing(user)
    setForm({ username: user.username, password: '', role: user.role, is_active: user.is_active })
    setShowForm(true)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (!editing && form.password.length < 8) {
      const message = 'Password must be at least 8 characters.'
      setError(message)
      notify.error('Could not save user', message)
      return
    }
    if (editing && form.password && form.password.length < 8) {
      const message = 'New password must be at least 8 characters.'
      setError(message)
      notify.error('Could not save user', message)
      return
    }
    setSubmitting(true)
    try {
      if (editing) {
        const body: Record<string, unknown> = { role: form.role, is_active: form.is_active }
        if (form.password) body.password = form.password
        await api.patch(`/api/v1/auth/users/${editing.id}`, body)
        notify.success('User updated', form.username)
      } else {
        await api.post('/api/v1/auth/users', {
          username: form.username.trim(),
          password: form.password,
          role: form.role,
        })
        notify.success('User created', form.username.trim())
      }
      resetForm()
      load()
    } catch (err) {
      setError(errorMessage(err))
      notify.error('Could not save user', errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  async function remove(user: UserAccount) {
    const ok = await confirmAction({
      title: `Delete user “${user.username}”?`,
      description: 'The account will immediately lose access. Audit history is retained.',
      confirmLabel: 'Delete user',
      danger: true,
    })
    if (!ok) return
    setError(null)
    try {
      await api.delete(`/api/v1/auth/users/${user.id}`)
      notify.success('User deleted', user.username)
      load()
    } catch (err) {
      setError(errorMessage(err))
      notify.error('Could not delete user', errorMessage(err))
    }
  }

  if (me?.role !== 'admin') {
    return (
      <>
        <PageHead title="Users" sub="Administrator account management" />
        <div className="card">
          <div className="empty">Administrator access is required to manage users.</div>
        </div>
      </>
    )
  }

  return (
    <>
      <PageHead
        title="Users"
        sub="Accounts and role assignments"
        actions={
          <button className="btn" onClick={startCreate}>
            <Icon name="plus" size={13} /> New user
          </button>
        }
      />
      <ErrorBanner message={error} />

      <Modal
        open={showForm}
        onOpenChange={(open) => {
          if (!open) resetForm()
          else setShowForm(true)
        }}
        title={editing ? `Edit ${editing.username}` : 'New user'}
        description={
          editing
            ? 'Change the role, active flag, or set a new password.'
            : 'Create an account with an initial password.'
        }
        footer={
          <>
            <button className="btn subtle" type="button" onClick={resetForm}>
              Cancel
            </button>
            <button className="btn" type="submit" form="user-form" disabled={submitting}>
              {submitting ? 'Saving…' : editing ? 'Save changes' : 'Create user'}
            </button>
          </>
        }
      >
        <form id="user-form" className="form-grid" onSubmit={submit}>
          <TextField
            label="Username"
            required={!editing}
            value={form.username}
            onChange={(v) => setForm({ ...form, username: v })}
            placeholder="jdoe"
            disabled={editing !== null}
          />
          <SelectField
            label="Role"
            required
            value={form.role}
            onChange={(v) => setForm({ ...form, role: v })}
            options={ROLES.map((r) => ({ value: r, label: r }))}
          />
          <TextField
            label={editing ? 'New password' : 'Password'}
            type="password"
            required={!editing}
            value={form.password}
            onChange={(v) => setForm({ ...form, password: v })}
            placeholder={editing ? 'Leave blank to keep current' : 'At least 8 characters'}
          />
          {editing ? (
            <SelectField
              label="Status"
              value={form.is_active ? 'active' : 'inactive'}
              onChange={(v) => setForm({ ...form, is_active: v === 'active' })}
              options={[
                { value: 'active', label: 'active' },
                { value: 'inactive', label: 'inactive' },
              ]}
              disabled={editing.id === me?.id}
            />
          ) : null}
        </form>
      </Modal>

      <div className="card">
        {!loaded ? (
          <Loading label="Loading users…" />
        ) : items.length === 0 ? (
          <div className="empty">No users found.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th className="no-print" />
                </tr>
              </thead>
              <tbody>
                {items.map((user) => (
                  <tr key={user.id}>
                    <td className="mono">
                      {user.username}
                      {user.id === me?.id ? <span className="small muted"> (you)</span> : null}
                    </td>
                    <td>
                      <span className={`badge role-${user.role}`}>{user.role}</span>
                    </td>
                    <td>
                      <span className={`badge ${user.is_active ? 'ok' : 'neutral'}`}>
                        {user.is_active ? 'active' : 'inactive'}
                      </span>
                    </td>
                    <td className="no-print">
                      <RowMenu
                        label={`Actions for ${user.username}`}
                        actions={[
                          {
                            label: 'Edit user',
                            icon: 'refresh' as const,
                            onSelect: () => startEdit(user),
                          },
                          {
                            label: 'Delete user',
                            icon: 'trash' as const,
                            danger: true,
                            onSelect: () => remove(user),
                            disabled: user.id === me?.id,
                          },
                        ]}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
