import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  api,
  errorMessage,
  type Environment,
  type Network,
  type NetworkDetail,
  type Paginated,
  type Subnet,
} from '../api'
import { Badge, ErrorBanner, ExportButtons, PageHead, Pagination, SuccessBanner } from '../ui'
import { kv } from '../kv'

const ENVIRONMENTS: Environment[] = ['production', 'staging', 'development', 'lab']

/* ------------------------------------------------------------------ */
/* Network list                                                       */
/* ------------------------------------------------------------------ */
function NetworkList() {
  const navigate = useNavigate()
  const [data, setData] = useState<Paginated<Network> | null>(null)
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    name: '',
    cidr: '',
    environment: 'production' as Environment,
    site: '',
    description: '',
  })

  const load = useCallback(() => {
    const params = new URLSearchParams({ page: String(page), page_size: '20' })
    if (q) params.set('q', q)
    api
      .get<Paginated<Network>>(`/api/v1/networks?${params}`)
      .then(setData)
      .catch((err) => setError(errorMessage(err)))
  }, [page, q])

  useEffect(() => {
    load()
  }, [load])

  async function create(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      const net = await api.post<Network>('/api/v1/networks', {
        name: form.name.trim(),
        cidr: form.cidr.trim(),
        environment: form.environment,
        site: form.site.trim() || null,
        description: form.description.trim() || null,
      })
      navigate(`/networks/${net.id}`)
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <>
      <PageHead
        title="Networks"
        sub="Parent address blocks and their allocation state"
        actions={
          <button className="btn" onClick={() => setShowForm((s) => !s)}>
            {showForm ? 'Close' : '+ New network'}
          </button>
        }
      />
      <ErrorBanner message={error} />

      {showForm && (
        <div className="card">
          <form className="form-grid" onSubmit={create}>
            <label className="field">
              Name *
              <input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="HQ LAN"
              />
            </label>
            <label className="field">
              CIDR *
              <input
                required
                value={form.cidr}
                onChange={(e) => setForm({ ...form, cidr: e.target.value })}
                placeholder="192.168.10.0/24"
              />
            </label>
            <label className="field">
              Environment
              <select
                value={form.environment}
                onChange={(e) => setForm({ ...form, environment: e.target.value as Environment })}
              >
                {ENVIRONMENTS.map((env) => (
                  <option key={env}>{env}</option>
                ))}
              </select>
            </label>
            <label className="field">
              Site
              <input
                value={form.site}
                onChange={(e) => setForm({ ...form, site: e.target.value })}
                placeholder="HQ"
              />
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
                Create network
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div className="inline no-print" style={{ marginBottom: 12 }}>
          <input
            style={{ maxWidth: 280 }}
            value={q}
            onChange={(e) => {
              setQ(e.target.value)
              setPage(1)
            }}
            placeholder="Search name, CIDR, site…"
          />
        </div>
        {!data || data.items.length === 0 ? (
          <div className="empty">No networks found.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>CIDR</th>
                  <th className="num">Family</th>
                  <th>Environment</th>
                  <th>Site</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((n) => (
                  <tr key={n.id}>
                    <td>
                      <Link to={`/networks/${n.id}`}>{n.name}</Link>
                    </td>
                    <td className="mono">{n.cidr}</td>
                    <td className="num">IPv{n.family}</td>
                    <td>{n.environment}</td>
                    <td>{n.site ?? '—'}</td>
                    <td>
                      <Badge status={n.status} />
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

/* ------------------------------------------------------------------ */
/* Network detail (with subnets)                                      */
/* ------------------------------------------------------------------ */
const SUBNET_STATUSES = ['allocated', 'reserved', 'released'] as const

function NetworkDetailView() {
  const { networkId } = useParams()
  const [net, setNet] = useState<NetworkDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [showSubnetForm, setShowSubnetForm] = useState(false)
  const [subnetForm, setSubnetForm] = useState({
    name: '',
    cidr: '',
    vlan_id: '',
    gateway: '',
    description: '',
  })

  const load = useCallback(() => {
    api
      .get<NetworkDetail>(`/api/v1/networks/${networkId}`)
      .then(setNet)
      .catch((err) => setError(errorMessage(err)))
  }, [networkId])

  useEffect(() => {
    load()
  }, [load])

  async function createSubnet(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    try {
      await api.post('/api/v1/subnets', {
        network_id: Number(networkId),
        name: subnetForm.name.trim(),
        cidr: subnetForm.cidr.trim(),
        vlan_id: subnetForm.vlan_id ? Number(subnetForm.vlan_id) : null,
        gateway: subnetForm.gateway.trim() || null,
        description: subnetForm.description.trim() || null,
      })
      setSuccess('Subnet allocated.')
      setSubnetForm({ name: '', cidr: '', vlan_id: '', gateway: '', description: '' })
      setShowSubnetForm(false)
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function setSubnetStatus(subnet: Subnet, status: string) {
    setError(null)
    try {
      await api.patch(`/api/v1/subnets/${subnet.id}`, { status })
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function removeSubnet(subnet: Subnet) {
    if (!window.confirm(`Delete subnet ${subnet.name} (${subnet.cidr})?`)) return
    setError(null)
    try {
      await api.delete(`/api/v1/subnets/${subnet.id}`)
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  if (!net) return <ErrorBanner message={error ?? 'Loading network…'} />

  const detailEntries = Object.entries(net.details).filter(
    ([, v]) => v !== null && v !== undefined && typeof v !== 'object',
  )

  return (
    <>
      <PageHead
        title={net.name}
        sub={`${net.cidr} · IPv${net.family} · ${net.environment}${net.site ? ` · ${net.site}` : ''}`}
        actions={
          <>
            <Badge status={net.status} />
            <ExportButtons base={`/api/v1/reports/networks/${net.id}`} />
          </>
        }
      />
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />

      <div className="grid cols-2">
        <div className="card">
          <h3>Computed properties</h3>
          <div className="kv">
            {detailEntries.map(([k, v]) => (
              <div key={k}>
                <div className="k">{k.replace(/_/g, ' ')}</div>
                <div className="v mono">{String(v)}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <h3>Metadata</h3>
          <div className="kv">
            {kv('Family', `IPv${net.family}`)}
            {kv('Environment', net.environment)}
            {kv('Site', net.site ?? '—')}
            {kv('Status', net.status)}
            {kv('Created', new Date(net.created_at).toLocaleString())}
            {kv('Updated', new Date(net.updated_at).toLocaleString())}
          </div>
          {net.description && <p className="muted">{net.description}</p>}
        </div>
      </div>

      <div className="card">
        <div className="page-head" style={{ marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>Subnets ({net.subnets.length})</h2>
          <button className="btn small no-print" onClick={() => setShowSubnetForm((s) => !s)}>
            {showSubnetForm ? 'Close' : '+ Allocate subnet'}
          </button>
        </div>

        {showSubnetForm && (
          <form className="form-grid no-print" onSubmit={createSubnet} style={{ marginBottom: 14 }}>
            <label className="field">
              Name *
              <input
                required
                value={subnetForm.name}
                onChange={(e) => setSubnetForm({ ...subnetForm, name: e.target.value })}
              />
            </label>
            <label className="field">
              CIDR *
              <input
                required
                value={subnetForm.cidr}
                onChange={(e) => setSubnetForm({ ...subnetForm, cidr: e.target.value })}
                placeholder="192.168.10.0/26"
              />
            </label>
            <label className="field">
              VLAN
              <input
                type="number"
                min={1}
                max={4094}
                value={subnetForm.vlan_id}
                onChange={(e) => setSubnetForm({ ...subnetForm, vlan_id: e.target.value })}
              />
            </label>
            <label className="field">
              Gateway
              <input
                value={subnetForm.gateway}
                onChange={(e) => setSubnetForm({ ...subnetForm, gateway: e.target.value })}
              />
            </label>
            <label className="field" style={{ gridColumn: '1 / -1' }}>
              Description
              <input
                value={subnetForm.description}
                onChange={(e) => setSubnetForm({ ...subnetForm, description: e.target.value })}
              />
            </label>
            <div className="form-actions">
              <button className="btn" type="submit">
                Allocate
              </button>
            </div>
          </form>
        )}

        {net.subnets.length === 0 ? (
          <div className="empty">No subnets yet.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>CIDR</th>
                  <th className="num">VLAN</th>
                  <th>Gateway</th>
                  <th className="num">IPs</th>
                  <th>Status</th>
                  <th className="no-print" />
                </tr>
              </thead>
              <tbody>
                {net.subnets.map((s) => (
                  <tr key={s.id}>
                    <td>{s.name}</td>
                    <td className="mono">{s.cidr}</td>
                    <td className="num">{s.vlan_id ?? '—'}</td>
                    <td className="mono">{s.gateway ?? '—'}</td>
                    <td className="num">{s.ip_address_count}</td>
                    <td>
                      <Badge status={s.status} />
                    </td>
                    <td className="no-print">
                      <select
                        value={s.status}
                        onChange={(e) => setSubnetStatus(s, e.target.value)}
                        style={{ width: 110 }}
                        title="Change status"
                      >
                        {SUBNET_STATUSES.map((st) => (
                          <option key={st}>{st}</option>
                        ))}
                      </select>{' '}
                      <button className="btn subtle small" onClick={() => removeSubnet(s)}>
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
    </>
  )
}

export default function Networks() {
  const { networkId } = useParams()
  return networkId ? <NetworkDetailView /> : <NetworkList />
}
