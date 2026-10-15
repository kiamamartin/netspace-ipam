import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, errorMessage, type IPAddress, type IPStatus, type Paginated, type Subnet } from '../api'
import { Badge, ErrorBanner, PageHead, Pagination, SuccessBanner } from '../ui'

const IP_STATUSES: IPStatus[] = ['assigned', 'available', 'reserved', 'deprecated']

export default function IpAddresses() {
  const [data, setData] = useState<Paginated<IPAddress> | null>(null)
  const [subnets, setSubnets] = useState<Subnet[]>([])
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [subnetId, setSubnetId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
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

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    api
      .get<Paginated<Subnet>>('/api/v1/subnets?page_size=200')
      .then((p) => setSubnets(p.items))
      .catch(() => setSubnets([]))
  }, [])

  async function register(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    try {
      await api.post('/api/v1/ip-addresses', {
        subnet_id: Number(form.subnet_id),
        address: form.address.trim(),
        hostname: form.hostname.trim() || null,
        device: form.device.trim() || null,
        status: form.status,
        description: form.description.trim() || null,
      })
      setSuccess(`Address ${form.address} registered.`)
      setForm({ subnet_id: '', address: '', hostname: '', device: '', status: 'assigned', description: '' })
      setShowForm(false)
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function changeStatus(row: IPAddress, next: IPStatus) {
    setError(null)
    try {
      await api.patch(`/api/v1/ip-addresses/${row.id}`, { status: next })
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function remove(row: IPAddress) {
    if (!window.confirm(`Remove ${row.address}?`)) return
    setError(null)
    try {
      await api.delete(`/api/v1/ip-addresses/${row.id}`)
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
          <button className="btn" onClick={() => setShowForm((s) => !s)}>
            {showForm ? 'Close' : '+ Register address'}
          </button>
        }
      />
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />

      {showForm && (
        <div className="card">
          <form className="form-grid" onSubmit={register}>
            <label className="field">
              Subnet *
              <select
                required
                value={form.subnet_id}
                onChange={(e) => setForm({ ...form, subnet_id: e.target.value })}
              >
                <option value="">Choose subnet…</option>
                {subnets.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} — {s.cidr}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Address *
              <input
                required
                value={form.address}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
                placeholder="192.168.10.10"
              />
            </label>
            <label className="field">
              Hostname
              <input
                value={form.hostname}
                onChange={(e) => setForm({ ...form, hostname: e.target.value })}
                placeholder="ws-01.hq"
              />
            </label>
            <label className="field">
              Device
              <input
                value={form.device}
                onChange={(e) => setForm({ ...form, device: e.target.value })}
                placeholder="laptop / printer / …"
              />
            </label>
            <label className="field">
              Status
              <select
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value as IPStatus })}
              >
                {IP_STATUSES.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
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
                Register
              </button>
            </div>
          </form>
        </div>
      )}

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
          <select
            style={{ width: 160 }}
            value={status}
            onChange={(e) => {
              setStatus(e.target.value)
              setPage(1)
            }}
          >
            <option value="">All statuses</option>
            {IP_STATUSES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <select
            style={{ width: 260 }}
            value={subnetId}
            onChange={(e) => {
              setSubnetId(e.target.value)
              setPage(1)
            }}
          >
            <option value="">All subnets</option>
            {subnets.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} — {s.cidr}
              </option>
            ))}
          </select>
        </div>

        {!data || data.items.length === 0 ? (
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
                      <select
                        value={row.status}
                        onChange={(e) => changeStatus(row, e.target.value as IPStatus)}
                        style={{ width: 120 }}
                      >
                        {IP_STATUSES.map((s) => (
                          <option key={s}>{s}</option>
                        ))}
                      </select>{' '}
                      <button className="btn subtle small" onClick={() => remove(row)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && (
          <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
        )}
      </div>
    </>
  )
}
