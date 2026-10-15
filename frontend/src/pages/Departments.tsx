import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, errorMessage, type Department, type Paginated } from '../api'
import { ErrorBanner, PageHead, SuccessBanner } from '../ui'

export default function Departments() {
  const [items, setItems] = useState<Department[]>([])
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState({
    name: '',
    description: '',
    default_host_requirement: 10,
    vlan_id: '',
    site: '',
  })

  const load = useCallback(() => {
    api
      .get<Paginated<Department>>('/api/v1/departments?page_size=200')
      .then((p) => setItems(p.items))
      .catch((err) => setError(errorMessage(err)))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  function startEdit(d: Department) {
    setEditingId(d.id)
    setForm({
      name: d.name,
      description: d.description ?? '',
      default_host_requirement: d.default_host_requirement,
      vlan_id: d.vlan_id ? String(d.vlan_id) : '',
      site: d.site ?? '',
    })
  }

  function resetForm() {
    setEditingId(null)
    setForm({ name: '', description: '', default_host_requirement: 10, vlan_id: '', site: '' })
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    const body = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      default_host_requirement: form.default_host_requirement,
      vlan_id: form.vlan_id ? Number(form.vlan_id) : null,
      site: form.site.trim() || null,
    }
    try {
      if (editingId) {
        await api.patch(`/api/v1/departments/${editingId}`, body)
        setSuccess(`Department "${body.name}" updated.`)
      } else {
        await api.post('/api/v1/departments', body)
        setSuccess(`Department "${body.name}" created.`)
      }
      resetForm()
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function remove(d: Department) {
    if (!window.confirm(`Delete department "${d.name}"?`)) return
    setError(null)
    try {
      await api.delete(`/api/v1/departments/${d.id}`)
      if (editingId === d.id) resetForm()
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <>
      <PageHead
        title="Departments"
        sub="Reusable organizational units with default planning values"
        actions={
          <button className="btn" onClick={resetForm}>
            + New department
          </button>
        }
      />
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />

      <div className="grid cols-2">
        <div className="card">
          <h3>{editingId ? 'Edit department' : 'Create department'}</h3>
          <form className="form-grid" onSubmit={submit}>
            <label className="field">
              Name *
              <input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </label>
            <label className="field">
              Default hosts
              <input
                type="number"
                min={1}
                value={form.default_host_requirement}
                onChange={(e) =>
                  setForm({ ...form, default_host_requirement: Number(e.target.value) })
                }
              />
            </label>
            <label className="field">
              Default VLAN
              <input
                type="number"
                min={1}
                max={4094}
                value={form.vlan_id}
                onChange={(e) => setForm({ ...form, vlan_id: e.target.value })}
              />
            </label>
            <label className="field">
              Site
              <input value={form.site} onChange={(e) => setForm({ ...form, site: e.target.value })} />
            </label>
            <label className="field" style={{ gridColumn: '1 / -1' }}>
              Description
              <input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </label>
            <div className="form-actions">
              <button className="btn" type="submit">
                {editingId ? 'Save changes' : 'Create'}
              </button>
              {editingId && (
                <button className="btn subtle" type="button" onClick={resetForm}>
                  Cancel
                </button>
              )}
            </div>
          </form>
        </div>

        <div className="card">
          <h3>Existing departments ({items.length})</h3>
          {items.length === 0 ? (
            <div className="empty">No departments defined yet.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th className="num">Default hosts</th>
                    <th className="num">VLAN</th>
                    <th>Site</th>
                    <th className="no-print" />
                  </tr>
                </thead>
                <tbody>
                  {items.map((d) => (
                    <tr key={d.id}>
                      <td>
                        <strong>{d.name}</strong>
                        {d.description && <div className="small muted">{d.description}</div>}
                      </td>
                      <td className="num">{d.default_host_requirement}</td>
                      <td className="num">{d.vlan_id ?? '—'}</td>
                      <td>{d.site ?? '—'}</td>
                      <td className="no-print">
                        <button className="btn subtle small" onClick={() => startEdit(d)}>
                          Edit
                        </button>{' '}
                        <button className="btn danger small" onClick={() => remove(d)}>
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
