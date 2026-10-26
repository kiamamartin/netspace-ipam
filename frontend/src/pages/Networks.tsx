import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { getUser } from '../auth'
import { api, errorMessage, type Environment,
  type Network,
  type NetworkDetail,
  type Paginated,
  type Subnet,
} from '../api'
import {
  Badge,
  CopyValue,
  ErrorBanner,
  ExportButtons,
  Icon,
  Loading,
  Modal,
  NumberField,
  PageHead,
  PaginationBar,
  RowMenu,
  SelectField,
  TextField,
} from '../ui'
import { confirmAction, notify } from '../feedback'
import { kv } from '../kv'

const ENVIRONMENTS: Environment[] = ['production', 'staging', 'development', 'lab']

/* ------------------------------------------------------------------ */
/* Network list                                                       */
/* ------------------------------------------------------------------ */
function NetworkList() {
  const navigate = useNavigate()
  const user = getUser()
  const [data, setData] = useState<Paginated<Network> | null>(null)
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
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
    setSubmitting(true)
    try {
      const net = await api.post<Network>('/api/v1/networks', {
        name: form.name.trim(),
        cidr: form.cidr.trim(),
        environment: form.environment,
        site: form.site.trim() || null,
        description: form.description.trim() || null,
      })
      notify.success('Network created', `${net.name} (${net.cidr})`)
      setShowForm(false)
      setForm({ name: '', cidr: '', environment: 'production', site: '', description: '' })
      navigate(`/networks/${net.id}`)
    } catch (err) {
      setError(errorMessage(err))
      notify.error('Could not create network', errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  async function setSubnetStatus(subnet: Subnet, status: string) {
    setError(null)
    if (user?.role === 'viewer') {
      notify.error('Cannot change subnet status in viewer role')
      return
    }
    try {
      await api.patch(`/api/v1/subnets/${subnet.id}`, { status })
      notify.success('Status updated', `${subnet.name} is now ${status}.`)
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function removeSubnet(subnet: Subnet) {
    // viewers cannot delete subnets
    if (user?.role === 'viewer') {
      notify.error('Subnets cannot be deleted in viewer role')
      return
    }
    setError(null)
    const ok = await confirmAction({
      title: `Delete subnet ${subnet.name}?`,
      description: `${subnet.cidr} and its tracked addresses will be removed from the inventory.`,
      confirmLabel: 'Delete subnet',
    })
    if (!ok) return
    setError(null)
    try {
      await api.delete(`/api/v1/subnets/${subnet.id}`)
      notify.success('Subnet deleted', subnet.name)
      load()
    } catch (err) {
      setError(errorMessage(err))
      notify.error('Could not delete subnet', errorMessage(err))
    }
  }

  return (
    <>
      <PageHead
        title="Networks"
        sub="Parent address blocks and their allocation state"
        actions={
          user?.role !== 'viewer' ? (
            <button className="btn" onClick={() => setShowForm(true)}>
              <Icon name="plus" size={13} /> New network
            </button>
          ) : null
        }
      />
      <ErrorBanner message={error} />

      <Modal
        open={showForm && user?.role !== 'viewer'}
        onOpenChange={setShowForm}
        title="New network"
        description="Register a parent address block in the inventory."
        wide
        footer={
          <>
            <button className="btn subtle" type="button" onClick={() => setShowForm(false)}>
              Cancel
            </button>
            <button className="btn" type="submit" form="create-network-form" disabled={submitting || user?.role === 'viewer'}>
              {submitting ? 'Creating…' : 'Create network'}
            </button>
          </>
        }
      >
        <form id="create-network-form" className="form-grid" onSubmit={create}>
          <TextField
            label="Name"
            required
            value={form.name}
            onChange={(v) => setForm({ ...form, name: v })}
            placeholder="HQ LAN"
          />
          <TextField
            label="CIDR"
            required
            value={form.cidr}
            onChange={(v) => setForm({ ...form, cidr: v })}
            placeholder="192.168.10.0/24"
            mono
          />
          <SelectField
            label="Environment"
            value={form.environment}
            onChange={(v) => setForm({ ...form, environment: v as Environment })}
            options={ENVIRONMENTS.map((env) => ({ value: env, label: env }))}
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
                    <td>
                      <CopyValue value={n.cidr} />
                    </td>
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
          <PaginationBar page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
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
  const user = getUser()
  const [net, setNet] = useState<NetworkDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showSubnetForm, setShowSubnetForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
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
    setSubmitting(true)
    try {
      await api.post('/api/v1/subnets', {
        network_id: Number(networkId),
        name: subnetForm.name.trim(),
        cidr: subnetForm.cidr.trim(),
        vlan_id: subnetForm.vlan_id ? Number(subnetForm.vlan_id) : null,
        gateway: subnetForm.gateway.trim() || null,
        description: subnetForm.description.trim() || null,
      })
      notify.success('Subnet allocated', `${subnetForm.name} (${subnetForm.cidr})`)
      setSubnetForm({ name: '', cidr: '', vlan_id: '', gateway: '', description: '' })
      setShowSubnetForm(false)
      load()
    } catch (err) {
      setError(errorMessage(err))
      notify.error('Could not allocate subnet', errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  async function setSubnetStatus(subnet: Subnet, status: string) {
    setError(null)
    try {
      await api.patch(`/api/v1/subnets/${subnet.id}`, { status })
      notify.success('Status updated', `${subnet.name} is now ${status}.`)
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function removeSubnet(subnet: Subnet) {
    const ok = await confirmAction({
      title: `Delete subnet ${subnet.name}?`,
      description: `${subnet.cidr} and its tracked addresses will be removed from the inventory.`,
      confirmLabel: 'Delete subnet',
    })
    if (!ok) return
    setError(null)
    try {
      await api.delete(`/api/v1/subnets/${subnet.id}`)
      notify.success('Subnet deleted', subnet.name)
      load()
    } catch (err) {
      setError(errorMessage(err))
      notify.error('Could not delete subnet', errorMessage(err))
    }
  }

  if (!net) return <Loading label="Loading network…" />

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
          {user?.role !== 'viewer' ? (
            <button className="btn small no-print" onClick={() => setShowSubnetForm(true)}>
              <Icon name="plus" size={13} /> Allocate subnet
            </button>
          ) : null}
        </div>

      <Modal
        open={showSubnetForm && user?.role !== 'viewer'}
        onOpenChange={setShowSubnetForm}
        title="Allocate subnet"
          description={`Carve a subnet out of ${net.cidr}.`}
          wide
        footer={
          <>
            <button className="btn subtle" type="button" onClick={() => setShowSubnetForm(false)}>
              Cancel
            </button>
            <button className="btn" type="submit" form="create-subnet-form" disabled={submitting || user?.role === 'viewer'}>
              {submitting ? 'Allocating…' : 'Allocate'}
            </button>
          </>
        }
        >
          <form id="create-subnet-form" className="form-grid" onSubmit={createSubnet}>
            <TextField
              label="Name"
              required
              value={subnetForm.name}
              onChange={(v) => setSubnetForm({ ...subnetForm, name: v })}
              placeholder="Staff LAN"
            />
            <TextField
              label="CIDR"
              required
              value={subnetForm.cidr}
              onChange={(v) => setSubnetForm({ ...subnetForm, cidr: v })}
              placeholder="192.168.10.0/26"
              mono
            />
            <NumberField
              value={subnetForm.vlan_id === '' ? '' : Number(subnetForm.vlan_id)}
              onChange={(v) => setSubnetForm({ ...subnetForm, vlan_id: String(v) })}
              min={1}
              max={4094}
              placeholder="VLAN id"
            />
            <TextField
              label="Gateway"
              value={subnetForm.gateway}
              onChange={(v) => setSubnetForm({ ...subnetForm, gateway: v })}
              placeholder="192.168.10.1"
              mono
            />
            <TextField
              label="Description"
              span
              value={subnetForm.description}
              onChange={(v) => setSubnetForm({ ...subnetForm, description: v })}
            />
          </form>
        </Modal>

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
                    <td>
                      <CopyValue value={s.cidr} />
                    </td>
                    <td className="num">{s.vlan_id ?? '—'}</td>
                    <td className="mono">{s.gateway ?? '—'}</td>
                    <td className="num">{s.ip_address_count}</td>
                    <td>
                      <Badge status={s.status} />
                    </td>
                    <td className="no-print">
                      <RowMenu
                        label={`Actions for ${s.name}`}
                        actions={[
                          ...SUBNET_STATUSES.filter((st) => st !== s.status).map((st) => ({
                            label: `Mark ${st}`,
                            icon: 'refresh' as const,
                            onSelect: () => setSubnetStatus(s, st),
                          })),
                          { label: 'Delete subnet', icon: 'trash' as const, danger: true, onSelect: () => removeSubnet(s), disabled: user?.role === 'viewer' },
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

export default function Networks() {
  const { networkId } = useParams()
  return networkId ? <NetworkDetailView /> : <NetworkList />
}
