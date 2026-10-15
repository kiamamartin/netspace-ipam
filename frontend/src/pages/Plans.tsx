import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  api,
  errorMessage,
  type Paginated,
  type Plan,
  type PlanListItem,
} from '../api'
import { Badge, ErrorBanner, ExportButtons, PageHead, SuccessBanner } from '../ui'

function PlanList() {
  const [items, setItems] = useState<PlanListItem[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .get<Paginated<PlanListItem>>('/api/v1/allocation-plans?page_size=100')
      .then((p) => setItems(p.items))
      .catch((err) => setError(errorMessage(err)))
  }, [])

  return (
    <>
      <PageHead
        title="Allocation Plans"
        sub="Saved VLSM plans — preview, activate and export"
        actions={
          <Link className="btn" to="/planner">
            New plan
          </Link>
        }
      />
      <ErrorBanner message={error} />
      <div className="card">
        {items.length === 0 ? (
          <div className="empty">
            No plans saved yet. Build one in the <Link to="/planner">VLSM Planner</Link>.
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Base network</th>
                  <th>Status</th>
                  <th className="num">Departments</th>
                  <th className="num">Utilization</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {items.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <Link to={`/plans/${p.id}`}>{p.name}</Link>
                    </td>
                    <td className="mono">{p.base_network}</td>
                    <td>
                      <Badge status={p.status} />
                    </td>
                    <td className="num">{p.department_count}</td>
                    <td className="num">{p.overall_utilization_percent.toFixed(1)}%</td>
                    <td className="small muted">{new Date(p.created_at).toLocaleDateString()}</td>
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

function PlanDetail() {
  const { planId } = useParams()
  const navigate = useNavigate()
  const [plan, setPlan] = useState<Plan | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [notes, setNotes] = useState('')

  const load = useCallback(() => {
    api
      .get<Plan>(`/api/v1/allocation-plans/${planId}`)
      .then((p) => {
        setPlan(p)
        setNotes(p.notes ?? '')
      })
      .catch((err) => setError(errorMessage(err)))
  }, [planId])

  useEffect(() => {
    load()
  }, [load])

  async function act(action: 'activate' | 'recalculate' | 'archive') {
    setError(null)
    setSuccess(null)
    setBusy(true)
    try {
      if (action === 'activate') {
        if (!window.confirm('Activate this plan? It will be committed to the inventory.'))
          return
        const res = await api.post<{ subnets_created: number }>(
          `/api/v1/allocation-plans/${planId}/activate`,
        )
        setSuccess(`Plan activated — ${res.subnets_created} subnet(s) created.`)
      } else if (action === 'recalculate') {
        await api.post(`/api/v1/allocation-plans/${planId}/recalculate`)
        setSuccess('Plan recalculated from stored inputs.')
      } else {
        if (!window.confirm('Archive this plan?')) return
        await api.post(`/api/v1/allocation-plans/${planId}/archive`)
        setSuccess('Plan archived.')
      }
      load()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function saveNotes() {
    setError(null)
    try {
      await api.patch(`/api/v1/allocation-plans/${planId}`, { notes })
      setSuccess('Notes saved.')
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  if (!plan) return <ErrorBanner message={error ?? 'Loading plan…'} />
  const results = plan.results

  return (
    <>
      <PageHead
        title={plan.name}
        sub={`${plan.base_network} · ${plan.status} · algorithm ${plan.algorithm_version}`}
        actions={
          <>
            <Badge status={plan.status} />
            <ExportButtons base={`/api/v1/reports/allocation-plans/${plan.id}`} />
            <button
              className="btn small"
              disabled={busy || plan.status !== 'draft'}
              onClick={() => act('activate')}
              title={plan.status !== 'draft' ? 'Only draft plans can be activated' : ''}
            >
              Activate
            </button>
            <button className="btn subtle small" disabled={busy} onClick={() => act('recalculate')}>
              Recalculate
            </button>
            <button
              className="btn danger small"
              disabled={busy || plan.status === 'archived'}
              onClick={() => act('archive')}
            >
              Archive
            </button>
          </>
        }
      />
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />

      <div className="card">
        <h3>Allocations</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="num">#</th>
                <th>Department</th>
                <th>Network</th>
                <th className="num">Prefix</th>
                <th className="num">Hosts req/eff</th>
                <th className="num">Usable</th>
                <th className="num">Util %</th>
                <th>Gateway</th>
                <th className="num">VLAN</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {results.allocations.map((a) => (
                <tr key={a.sequence}>
                  <td className="num">{a.sequence}</td>
                  <td>{a.department}</td>
                  <td className="mono">{a.network}</td>
                  <td className="num">/{a.prefix_length}</td>
                  <td className="num">
                    {a.requested_hosts} / {a.effective_hosts}
                  </td>
                  <td className="num">{a.usable_capacity}</td>
                  <td className="num">{a.utilization_percent.toFixed(1)}</td>
                  <td className="mono">{a.gateway ?? '—'}</td>
                  <td className="num">{a.vlan_id ?? '—'}</td>
                  <td>
                    <Badge status={a.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <h3 style={{ marginTop: 16 }}>Remaining ranges</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Start</th>
                <th>End</th>
                <th className="num">Total</th>
                <th className="num">Usable</th>
              </tr>
            </thead>
            <tbody>
              {results.remaining_ranges.length === 0 ? (
                <tr>
                  <td colSpan={4} className="empty">
                    None — base network fully allocated.
                  </td>
                </tr>
              ) : (
                results.remaining_ranges.map((r, i) => (
                  <tr key={i}>
                    <td className="mono">{r.start}</td>
                    <td className="mono">{r.end}</td>
                    <td className="num">{r.total_addresses}</td>
                    <td className="num">{r.usable_hosts}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h3>Notes</h3>
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} />
        <div className="form-actions no-print">
          <button className="btn small" onClick={saveNotes}>
            Save notes
          </button>
          <button className="btn ghost small" onClick={() => navigate('/plans')}>
            ← Back to plans
          </button>
        </div>
      </div>
    </>
  )
}

export default function Plans() {
  const { planId } = useParams()
  return planId ? <PlanDetail /> : <PlanList />
}
