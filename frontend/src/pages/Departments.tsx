import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { getUser } from '../auth'
import { api, errorMessage, type Department, type Paginated } from '../api'
import {
  ErrorBanner,
  Icon,
  Loading,
  Modal,
  NumberField,
  PageHead,
  RowMenu,
  TextField,
} from '../ui'
import { confirmAction, notify } from '../feedback'

export default function Departments() {
  const [items, setItems] = useState<Department[]>([])
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState({
    name: '',
    description: '',
    default_host_requirement: 10,
    vlan_id: '',
    site: '',
  })
  const user = getUser()

  const load = useCallback(() => {
    api
      .get<Paginated<Department>>('/api/v1/departments?page_size=200')
      .then((p) => setItems(p.items))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoaded(true))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  function startEdit(d: Department) {      if (user?.role === 'viewer') {
      notify.error('Departments cannot be edited in viewer role')
      return
    }
    setEditingId(d.id)
    setForm({
      name: d.name,
      description: d.description ?? '',
      default_host_requirement: d.default_host_requirement,
      vlan_id: d.vlan_id ? String(d.vlan_id) : '',
      site: d.site ?? '',
    })
    setShowForm(true)
  }

  function resetForm() {
    setEditingId(null)
    setForm({ name: '', description: '', default_host_requirement: 10, vlan_id: '', site: '' })
    setShowForm(false)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
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
        notify.success('Department updated', `“${body.name}” was saved.`)
      } else {
        await api.post('/api/v1/departments', body)
        notify.success('Department created', `“${body.name}” is ready for planning.`)
      }
      resetForm()
      load()
    } catch (err) {
      setError(errorMessage(err))
      notify.error('Could not save department', errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  async function remove(d: Department) {
    // viewers cannot delete; operator+admin confirm
    if (user?.role === 'viewer') {
      notify.error('Departments cannot be deleted in viewer role')
      return
    }
    const ok = await confirmAction({
      title: `Delete department “${d.name}”?`,
      description: 'Saved plans keep their own copies of the allocation data.',
      confirmLabel: 'Delete department',
    })
    if (!ok) return
    setError(null)
    try {
      await api.delete(`/api/v1/departments/${d.id}`)
      if (editingId === d.id) resetForm()
      notify.success('Department deleted', d.name)
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
          user?.role !== 'viewer' ? (
            <button className="btn" onClick={() => { resetForm(); setShowForm(true) }}>
              <Icon name="plus" size={13} /> New department
            </button>
          ) : null
        }
      />
      <ErrorBanner message={error} />        <Modal
        open={showForm}
        onOpenChange={(open) => {
          if (!open) { resetForm(); setShowForm(false) }
          else if (user?.role === 'viewer' && editingId == null) setShowForm(false)
          else setShowForm(open)
        }}
        title={editingId ? 'Edit department' : 'New department'}
        description="Departments carry reusable default planning values into the VLSM planner."
        wide
        footer={
          <>
            <button className="btn subtle" type="button" onClick={resetForm}>
              Cancel
            </button>
            <button className="btn" type="submit" form="department-form" disabled={submitting || user?.role === 'viewer'}>
              {submitting ? 'Saving…' : editingId ? 'Save changes' : 'Create department'}
            </button>
          </>
        }
      >
        <form id="department-form" className="form-grid" onSubmit={submit}>
          <TextField
            label="Name"
            required
            value={form.name}
            onChange={(v) => setForm({ ...form, name: v })}
          />
          <NumberField
            value={form.default_host_requirement}
            onChange={(v) => setForm({ ...form, default_host_requirement: v })}
            min={1}
            placeholder="Default hosts"
          />
          <NumberField
            value={form.vlan_id === '' ? '' : Number(form.vlan_id)}
            onChange={(v) => setForm({ ...form, vlan_id: String(v) })}
            min={1}
            max={4094}
            placeholder="Default VLAN"
          />
          <TextField
            label="Site"
            value={form.site}
            onChange={(v) => setForm({ ...form, site: v })}
            placeholder="HQ"
          />
          <TextField
            label="Description"
            span
            value={form.description}
            onChange={(v) => setForm({ ...form, description: v })}
          />
        </form>
      </Modal>

      <div className="grid cols-1">
        <div className="card">
          <h3>Existing departments ({items.length})</h3>
          {!loaded ? (
            <Loading label="Loading departments…" />
          ) : items.length === 0 ? (
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
                        <RowMenu
                          label={`Actions for ${d.name}`}
                          actions={[
                            { label: 'Edit department', icon: 'edit' as const, onSelect: () => startEdit(d) },
                            {label: 'Delete department', icon: 'trash' as const, danger: true, onSelect: () => remove(d), disabled: user?.role === 'viewer'}
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
      </div>
    </>
  )
}
