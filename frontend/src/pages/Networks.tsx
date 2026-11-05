import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { getUser } from '../auth'
import { ApiError, api, errorMessage, type Environment,
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
  HistoryModal,
  Icon,
  Loading,
  Meter,
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
  const [status, setStatus] = useState('')
  const [environment, setEnvironment] = useState('')
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
    if (status) params.set('status', status)
    if (environment) params.set('environment', environment)
    api
      .get<Paginated<Network>>(`/api/v1/networks?${params}`)
      .then(setData)
      .catch((err) => setError(errorMessage(err)))
  }, [page, q, status, environment])

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
          <div style={{ width: 160 }}>
            <SelectField
              label="Status"
              hideLabel
              value={status}
              onChange={(v) => {
                setStatus(v)
                setPage(1)
              }}
              options={['active', 'planned', 'deprecated'].map((s) => ({ value: s, label: s }))}
              placeholder="All statuses"
            />
          </div>
          <div style={{ width: 180 }}>
            <SelectField
              label="Environment"
              hideLabel
              value={environment}
              onChange={(v) => {
                setEnvironment(v)
                setPage(1)
              }}
              options={ENVIRONMENTS.map((e) => ({ value: e, label: e }))}
              placeholder="All environments"
            />
          </div>
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
const SUBNET_STATUSES = ['allocated', 'planned', 'reserved', 'released'] as const
const SUBNET_MANUAL_STATUSES = ['allocated', 'planned'] as const

function NetworkDetailView() {
  const { networkId } = useParams()
  const user = getUser()
  const [net, setNet] = useState<NetworkDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showSubnetForm, setShowSubnetForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [historySubnet, setHistorySubnet] = useState<Subnet | null>(null)
  const [subnetQuery, setSubnetQuery] = useState('')
  const [subnetStatusFilter, setSubnetStatusFilter] = useState('')
  const [subnetForm, setSubnetForm] = useState({
    name: '',
    cidr: '',
    vlan_id: '',
    gateway: '',
    owner: '',
    location: '',
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
        owner: subnetForm.owner.trim() || null,
        location: subnetForm.location.trim() || null,
        description: subnetForm.description.trim() || null,
      })
      notify.success('Subnet allocated', `${subnetForm.name} (${subnetForm.cidr})`)
      setSubnetForm({ name: '', cidr: '', vlan_id: '', gateway: '', owner: '', location: '', description: '' })
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

  async function reserveSubnet(subnet: Subnet) {
    setError(null)
    try {
      await api.post(`/api/v1/subnets/${subnet.id}/reserve`)
      notify.success('Subnet reserved', `${subnet.name} is held for future use.`)
      load()
    } catch (err) {
      setError(errorMessage(err))
      notify.error('Could not reserve subnet', errorMessage(err))
    }
  }

  async function releaseSubnet(subnet: Subnet) {
    const ok = await confirmAction({
      title: `Release subnet ${subnet.name}?`,
      description: `${subnet.cidr} returns to unallocated space. The record and its history are kept.`,
      confirmLabel: 'Release subnet',
    })
    if (!ok) return
    setError(null)
    try {
      try {
        await api.post(`/api/v1/subnets/${subnet.id}/release`)
      } catch (err) {
        if (!(err instanceof ApiError) || err.code !== 'subnet_not_empty') throw err
        const force = await confirmAction({
          title: 'Subnet still has addresses',
          description: 'Assigned or reserved addresses exist. Release anyway and leave them historical?',
          confirmLabel: 'Force release',
        })
        if (!force) return
        await api.post(`/api/v1/subnets/${subnet.id}/release?force=true`)
      }
      notify.success('Subnet released', subnet.name)
      load()
    } catch (err) {
      setError(errorMessage(err))
      notify.error('Could not release subnet', errorMessage(err))
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

  const needle = subnetQuery.trim().toLowerCase()
  const visibleSubnets = net.subnets.filter(
    (s) =>
      (!subnetStatusFilter || s.status === subnetStatusFilter) &&
      (!needle ||
        [s.name, s.cidr, s.gateway, s.owner, s.location, s.description]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(needle))),
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
          <h2 style={{ margin: 0 }}>
            Subnets ({visibleSubnets.length}
            {visibleSubnets.length !== net.subnets.length ? ` of ${net.subnets.length}` : ''})
          </h2>
          <div className="inline no-print">
            <input
              style={{ maxWidth: 220 }}
              value={subnetQuery}
              onChange={(e) => setSubnetQuery(e.target.value)}
              placeholder="Filter name, CIDR, owner…"
            />
            <div style={{ width: 160 }}>
              <SelectField
                label="Subnet status"
                hideLabel
                value={subnetStatusFilter}
                onChange={setSubnetStatusFilter}
                options={SUBNET_STATUSES.map((s) => ({ value: s, label: s }))}
                placeholder="All statuses"
              />
            </div>
            {user?.role !== 'viewer' ? (
              <button className="btn small no-print" onClick={() => setShowSubnetForm(true)}>
                <Icon name="plus" size={13} /> Allocate subnet
              </button>
            ) : null}
          </div>
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
              label="VLAN id"
            />
            <TextField
              label="Gateway"
              value={subnetForm.gateway}
              onChange={(v) => setSubnetForm({ ...subnetForm, gateway: v })}
              placeholder="192.168.10.1"
              mono
            />
            <TextField
              label="Owner"
              value={subnetForm.owner}
              onChange={(v) => setSubnetForm({ ...subnetForm, owner: v })}
              placeholder="IT Voice Team"
            />
            <TextField
              label="Location"
              value={subnetForm.location}
              onChange={(v) => setSubnetForm({ ...subnetForm, location: v })}
              placeholder="HQ comms room A"
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
        ) : visibleSubnets.length === 0 ? (
          <div className="empty">No subnets match the current filters.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>CIDR</th>
                  <th className="num">VLAN</th>
                  <th>Gateway</th>
                  <th>Owner</th>
                  <th>Location</th>
                  <th className="num">IPs</th>
                  <th>Utilization</th>
                  <th>Status</th>
                  <th className="no-print" />
                </tr>
              </thead>
              <tbody>
                {visibleSubnets.map((s) => {
                  const util = s.utilization
                  return (
                    <tr key={s.id}>
                      <td>{s.name}</td>
                      <td>
                        <CopyValue value={s.cidr} />
                      </td>
                      <td className="num">{s.vlan_id ?? '—'}</td>
                      <td className="mono">{s.gateway ?? '—'}</td>
                      <td>{s.owner ?? '—'}</td>
                      <td>{s.location ?? '—'}</td>
                      <td className="num">{s.ip_address_count}</td>
                      <td>
                        {util ? (
                          <>
                            <Meter percent={util.ip_utilization_percent} hot={util.ip_utilization_percent >= 85} />
                            <span className="small muted">
                              {util.assigned_addresses + util.reserved_addresses}/{util.usable_addresses} ·{' '}
                              {util.remaining_usable} free
                            </span>
                          </>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td>
                        <Badge status={s.status} />
                      </td>
                      <td className="no-print">
                        <RowMenu
                          label={`Actions for ${s.name}`}
                          actions={[
                            ...SUBNET_MANUAL_STATUSES.filter((st) => st !== s.status).map((st) => ({
                              label: `Mark ${st}`,
                              icon: 'refresh' as const,
                              onSelect: () => setSubnetStatus(s, st),
                              disabled: user?.role === 'viewer',
                            })),
                            ...(s.status !== 'reserved' && s.status !== 'released'
                              ? [{
                                  label: 'Reserve subnet',
                                  icon: 'archive' as const,
                                  onSelect: () => reserveSubnet(s),
                                  disabled: user?.role === 'viewer',
                                }]
                              : []),
                            ...(s.status !== 'released'
                              ? [{
                                  label: 'Release subnet',
                                  icon: 'power' as const,
                                  danger: true,
                                  onSelect: () => releaseSubnet(s),
                                  disabled: user?.role === 'viewer',
                                }]
                              : []),
                            {
                              label: 'View history',
                              icon: 'eye' as const,
                              onSelect: () => setHistorySubnet(s),
                            },
                            { label: 'Delete subnet', icon: 'trash' as const, danger: true, onSelect: () => removeSubnet(s), disabled: user?.role === 'viewer' },
                          ]}
                        />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        <HistoryModal
          open={historySubnet !== null}
          onOpenChange={(open) => {
            if (!open) setHistorySubnet(null)
          }}
          title={historySubnet ? `History — ${historySubnet.name}` : 'Subnet history'}
          path={historySubnet ? `/api/v1/subnets/${historySubnet.id}/history` : ''}
        />
      </div>
    </>
  )
}

export default function Networks() {
  const { networkId } = useParams()
  return networkId ? <NetworkDetailView /> : <NetworkList />
}
