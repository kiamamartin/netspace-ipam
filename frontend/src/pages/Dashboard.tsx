import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, errorMessage, type AuditEvent, type DashboardSummary } from '../api'
import { ErrorBanner, Meter, PageHead } from '../ui'
import { kv } from '../kv'

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [audit, setAudit] = useState<AuditEvent[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    Promise.all([
      api.get<DashboardSummary>('/api/v1/dashboard/summary'),
      api.get<{ items: AuditEvent[] }>('/api/v1/audit-events?page_size=12'),
    ])
      .then(([s, a]) => {
        if (!alive) return
        setSummary(s)
        setAudit(a.items)
      })
      .catch((err) => alive && setError(errorMessage(err)))
    return () => {
      alive = false
    }
  }, [])

  if (error) return <ErrorBanner message={error} />
  if (!summary) return <div className="muted">Loading dashboard…</div>

  const ipTotal =
    summary.ip_available + summary.ip_reserved + summary.ip_assigned + summary.ip_deprecated

  return (
    <>
      <PageHead title="Dashboard" sub="IPAM posture across all networks" />
      <div className="grid cols-4">
        <div className="stat">
          <div className="label">Networks</div>
          <div className="value">{summary.total_networks}</div>
          <div className="hint">{summary.total_subnets} subnets allocated</div>
        </div>
        <div className="stat">
          <div className="label">IP addresses</div>
          <div className="value">{summary.total_ip_addresses}</div>
          <div className="hint">
            {summary.ip_assigned} assigned · {summary.ip_available} free
          </div>
        </div>
        <div className="stat">
          <div className="label">Avg utilization</div>
          <div className="value">{summary.average_utilization_percent.toFixed(1)}%</div>
          <div className="hint">of allocated address space</div>
        </div>
        <div className="stat">
          <div className="label">Plans</div>
          <div className="value">{summary.total_plans}</div>
          <div className="hint">{summary.active_plans} active</div>
        </div>
      </div>

      {summary.conflicts.length > 0 && (
        <div className="banner error" style={{ marginTop: 16 }}>
          <strong>{summary.conflicts.length} conflict(s) detected:</strong>{' '}
          {summary.conflicts.map((c, i) => (
            <span key={i}>{JSON.stringify(c)} </span>
          ))}
        </div>
      )}

      <div className="grid cols-2" style={{ marginTop: 18 }}>
        <div className="card">
          <h3>Network utilization</h3>
          {summary.networks.length === 0 ? (
            <div className="empty">No networks yet — create one under Networks.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Network</th>
                    <th>CIDR</th>
                    <th className="num">Subnets</th>
                    <th style={{ width: '30%' }}>Utilization</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.networks.map((n) => (
                    <tr key={n.network_id}>
                      <td>
                        <Link to={`/networks/${n.network_id}`}>{n.name}</Link>
                      </td>
                      <td className="mono">{n.cidr}</td>
                      <td className="num">{n.subnet_count}</td>
                      <td>
                        <Meter percent={n.utilization_percent} hot={n.utilization_percent >= 85} />
                        <span className="small muted">
                          {n.utilization_percent.toFixed(1)}% ·{' '}
                          {n.allocated_addresses.toLocaleString()}/
                          {n.total_addresses.toLocaleString()}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {summary.near_capacity.length > 0 && (
            <>
              <h3 style={{ marginTop: 16 }}>Near capacity</h3>
              <div className="warn-list">
                {summary.near_capacity.map((n) => (
                  <div key={n.network_id}>
                    {n.name} ({n.cidr}) — {n.utilization_percent.toFixed(1)}% used
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="card">
          <h3>Address space</h3>
          <div className="kv">
            {kv('Assigned', summary.ip_assigned)}
            {kv('Reserved', summary.ip_reserved)}
            {kv('Available', summary.ip_available)}
            {kv('Deprecated', summary.ip_deprecated)}
            {kv(
              'Tracked',
              ipTotal.toLocaleString(),
            )}
          </div>

          <h3 style={{ marginTop: 20 }}>Recent activity</h3>
          {audit.length === 0 ? (
            <div className="empty">No audit events yet.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Action</th>
                    <th>Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.map((e) => (
                    <tr key={e.id}>
                      <td className="small muted">{new Date(e.timestamp).toLocaleString()}</td>
                      <td>
                        <span className="badge neutral">{e.action}</span>{' '}
                        <span className="small muted">
                          {e.resource_type} #{e.resource_id}
                        </span>
                      </td>
                      <td className="small">{e.summary}</td>
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
