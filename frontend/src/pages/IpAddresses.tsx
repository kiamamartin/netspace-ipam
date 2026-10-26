import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { getUser } from '../auth'
import { api, errorMessage, type IPAddress, type IPStatus, type Paginated, type Subnet } from '../api'
import {
  Badge,
  ErrorBanner,
  Icon,
  Loading,
  Modal,
  PageHead,
  PaginationBar,
  RowMenu,
  SelectField,
  TextField,
} from '../ui'
import { confirmAction, notify } from '../feedback'

export default function IpAddresses() {
  const [data, setData] = useState<Paginated<IPAddress> | null>(null)
  const [subnets, setSubnets] = useState<Subnet[]>([])
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [subnetId, setSubnetId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const user = getUser()
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState({
    subnet_id: '',
    address: '',
    hostname: '',
    device: '',
    status: 'assigned' as IPStatus,
    description: '',
  })

  const load = useCallback(() => {
    const params = new URLSearchParams({ page: String(page), page_size: '25' })
    if (q) params.set('q', q)
    if (status) params.set('status', status)
    if (subnetId) params.set('subnet_id', subnetId)
    api
      .get<Paginated<IPAddress>>(`/api/v1/ip-addresses?${params}`)
      .then(setData)
      .catch((err) => setError(errorMessage(err)))
  }, [page, q, status, subnetId])

  // Reload whenever the query, filters or page change.
  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    api
      .get<Paginated<Subnet>>('/api/v1/subnets?page_size=200')
      .then((p) => {
        setSubnets(p.items)
      })
      .catch(() => {
        setSubnets([])
      })
  }, [])

  const IP_STATUSES: IPStatus[] = ['assigned', 'available', 'reserved', 'deprecated']

  async function register(e: FormEvent) {
    e.preventDefault()
    if (user?.role === 'viewer') {
      notify.error('Addresses cannot be registered in viewer role')
      return
    }
    const subnetId = Number(form.subnet_id)
    if (!form.subnet_id || isNaN(subnetId) || subnetId < 1) {
      notify.error('Choose a subnet')
      return
    }
    if (!form.address.trim()) {
      notify.error('Enter an address')
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      await api.post('/api/v1/ip-addresses', {
        subnet_id: subnetId,
        address: form.address.trim(),
        hostname: form.hostname.trim() || null,
        device: form.device.trim() || null,
        status: form.status,
        description: form.description.trim() || null,
      })
      notify.success('Address registered', form.address)
      setForm({ subnet_id: '', address: '', hostname: '', device: '', status: 'assigned', description: '' })
      setShowForm(false)
      load()
    } catch (err) {
      setError(errorMessage(err))
      notify.error('Could not register address', errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  async function changeStatus(row: IPAddress, next: IPStatus) {
    setError(null)
    if (user?.role === 'viewer') {
      notify.error('Cannot change IP status in viewer role')
      return
    }
    try {
      await api.patch(`/api/v1/ip-addresses/${row.id}`, { status: next })
      notify.success('Status updated', `${row.address} is now ${next}.`)
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function remove(row: IPAddress) {
    // viewers cannot remove addresses
    if (user?.role === 'viewer') {
      notify.error('Addresses cannot be removed in viewer role')
      return
    }
    const ok = await confirmAction({
      title: `Remove ${row.address}?`,
      description: 'The tracked address will be deleted from the inventory.',
      confirmLabel: 'Remove address',
    })
    if (!ok) return
    setError(null)
    try {
      await api.delete(`/api/v1/ip-addresses/${row.id}`)
      notify.success('Address removed', row.address)
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  const subnetLabel = (id: number) => {
    const s = subnets.find((x) => x.id === id)
    return s ? `${s.name} (${s.cidr})` : `#${id}`
  }

  return (
    <>
      <PageHead
        title="IP Addresses"
        sub="Tracked host addresses inside allocated subnets"
        actions={
          user?.role !== 'viewer' ? (
            <button className="btn" onClick={() => { setShowForm(true) }}>
              <Icon name="plus" size={13} /> Register address
            </button>
          ) : null
        }
      />
      <ErrorBanner message={error} />

      <Modal
        open={showForm}
        onOpenChange={setShowForm}
        title="Register IP address"
        description="Track a host address inside an allocated subnet."
        wide
        footer={
          <>
            <button className="btn subtle" type="button" onClick={() => setShowForm(false)}>
              Cancel
            </button>
            <button className="btn" type="submit" form="register-ip-form" disabled={submitting || user?.role === 'viewer'}>
              {submitting ? 'Registering…' : 'Register'}
            </button>
          </>
        }
      >
        <form id="register-ip-form" className="form-grid" onSubmit={register}>
          <SelectField
            label="Subnet"
            required
            value={form.subnet_id}
            onChange={(v) => setForm({ ...form, subnet_id: v })}
            options={subnets.map((s) => ({ value: String(s.id), label: `${s.name} — ${s.cidr}` }))}
            placeholder="Choose subnet…"
            span
          />
          <TextField
            label="Address"
            required
            value={form.address}
            onChange={(v) => setForm({ ...form, address: v })}
            placeholder="192.168.10.10"
            mono
          />
          <SelectField
            label="Status"
            value={form.status}
            onChange={(v) => setForm({ ...form, status: v as IPStatus })}
            options={IP_STATUSES.map((s) => ({ value: s, label: s }))}
          />
          <TextField
            label="Hostname"
            value={form.hostname}
            onChange={(v) => setForm({ ...form, hostname: v })}
            placeholder="ws-01.hq"
          />
          <TextField
            label="Device"
            value={form.device}
            onChange={(v) => setForm({ ...form, device: v })}
            placeholder="laptop / printer / …"
          />
          <TextField
            label="Description"
            span
            value={form.description}
            onChange={(v) => setForm({ ...form, description: v })}
          />
        </form>
      </Modal>

      <div className="card">
        <div className="inline no-print" style={{ marginBottom: 12 }}>
          <input
            style={{ maxWidth: 240 }}
            value={q}
            onChange={(e) => {
              setQ(e.target.value)
              setPage(1)
            }}
            placeholder="Search address, host, device…"
          />
          <div style={{ width: 160 }}>
            <SelectField
              label="Status"
              hideLabel
              value={status}
              onChange={(v) => {
                setStatus(v)
                setPage(1)
              }}
              options={IP_STATUSES.map((s) => ({ value: s, label: s }))}
              placeholder="All statuses"
            />
          </div>
          <div style={{ width: 260 }}>
            <SelectField
              label="Subnet"
              hideLabel
              value={subnetId}
              onChange={(v) => {
                setSubnetId(v)
                setPage(1)
              }}
              options={subnets.map((s) => ({ value: String(s.id), label: `${s.name} — ${s.cidr}` }))}
              placeholder="All subnets"
            />
          </div>
        </div>

        {!data ? (
          <Loading label="Loading addresses…" />
        ) : data.items.length === 0 ? (
          <div className="empty">No addresses match.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Address</th>
                  <th>Subnet</th>
                  <th>Hostname</th>
                  <th>Device</th>
                  <th>Status</th>
                  <th className="no-print" />
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => (
                  <tr key={row.id}>
                    <td className="mono">{row.address}</td>
                    <td className="small">{subnetLabel(row.subnet_id)}</td>
                    <td>{row.hostname ?? '—'}</td>
                    <td>{row.device ?? '—'}</td>
                    <td>
                      <Badge status={row.status} />
                    </td>
                    <td className="no-print">
                      <RowMenu
                        label={`Actions for ${row.address}`}
                        actions={[
                          ...IP_STATUSES.filter((s) => s !== row.status).map((s) => ({
                            label: `Mark ${s}`,
                            icon: 'refresh' as const,
                            onSelect: () => changeStatus(row, s),
                          })),
                          { label: 'Remove address', icon: 'trash' as const, danger: true, onSelect: () => remove(row), disabled: user?.role === 'viewer' },
                        ]}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && (
          <PaginationBar page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
        )}
      </div>
    </>
  )
}
