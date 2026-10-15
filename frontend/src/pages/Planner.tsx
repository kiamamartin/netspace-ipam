import { useMemo, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, errorMessage, type VlsmResult } from '../api'
import { ErrorBanner, PageHead, SuccessBanner } from '../ui'

interface DeptRow {
  key: number
  name: string
  required_hosts: number
  vlan_id: string
  gateway: string
  additional_reserved_addresses: number
  growth_percent: string
  prefix_length: string
}

let nextKey = 1
const blankRow = (name: string, hosts: number): DeptRow => ({
  key: nextKey++,
  name,
  required_hosts: hosts,
  vlan_id: '',
  gateway: '',
  additional_reserved_addresses: 0,
  growth_percent: '',
  prefix_length: '',
})

export default function Planner() {
  const navigate = useNavigate()
  const [base, setBase] = useState('192.168.10.0/24')
  const [growth, setGrowth] = useState('0')
  const [rows, setRows] = useState<DeptRow[]>([
    blankRow('Administration', 50),
    blankRow('ICT', 25),
    blankRow('Finance', 20),
    blankRow('Human Resources', 12),
    blankRow('Guest Network', 10),
  ])
  const [planName, setPlanName] = useState('')
  const [notes, setNotes] = useState('')
  const [result, setResult] = useState<VlsmResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const update = (key: number, patch: Partial<DeptRow>) =>
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)))

  const payload = useMemo(() => {
    const departments = rows
      .filter((r) => r.name.trim())
      .map((r) => {
        const d: Record<string, unknown> = {
          name: r.name.trim(),
          required_hosts: r.required_hosts,
        }
        if (r.vlan_id) d.vlan_id = Number(r.vlan_id)
        if (r.gateway) d.gateway = r.gateway.trim()
        if (r.additional_reserved_addresses)
          d.additional_reserved_addresses = r.additional_reserved_addresses
        if (r.growth_percent) d.growth_percent = Number(r.growth_percent)
        if (r.prefix_length) d.prefix_length = Number(r.prefix_length)
        return d
      })
    const policy: Record<string, unknown> = {}
    if (growth) policy.growth_percent = Number(growth)
    return { base_network: base, departments, policy }
  }, [rows, base, growth])

  async function preview(e?: FormEvent) {
    e?.preventDefault()
    setError(null)
    setSuccess(null)
    setBusy(true)
    try {
      const res = await api.post<VlsmResult>('/api/v1/calculator/vlsm', payload)
      setResult(res)
    } catch (err) {
      setError(errorMessage(err))
      setResult(null)
    } finally {
      setBusy(false)
    }
  }

  async function savePlan() {
    if (!planName.trim()) {
      setError('Give the plan a name before saving.')
      return
    }
    setError(null)
    setSuccess(null)
    setBusy(true)
    try {
      const plan = await api.post<{ id: number }>('/api/v1/allocation-plans', {
        name: planName.trim(),
        notes: notes || null,
        ...payload,
      })
      setSuccess(`Plan saved — opening it…`)
      navigate(`/plans/${plan.id}`)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHead
        title="VLSM Planner"
        sub="Describe requirements, preview the allocation, then save it as a plan"
      />
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />

      <div className="card">
        <form className="form-grid" onSubmit={preview}>
          <label className="field">
            Parent network (CIDR)
            <input value={base} onChange={(e) => setBase(e.target.value)} />
          </label>
          <label className="field">
            Default growth allowance (%)
            <input value={growth} onChange={(e) => setGrowth(e.target.value)} inputMode="decimal" />
          </label>
          <div className="form-actions" style={{ alignSelf: 'end' }}>
            <button className="btn" type="submit" disabled={busy}>
              {busy ? 'Working…' : 'Preview allocation'}
            </button>
            <button
              className="btn ghost"
              type="button"
              onClick={() => setRows((rs) => [...rs, blankRow('', 10)])}
            >
              + Add department
            </button>
          </div>
        </form>

        <div className="table-wrap" style={{ marginTop: 14 }}>
          <table>
            <thead>
              <tr>
                <th>Department</th>
                <th className="num">Hosts</th>
                <th className="num">VLAN</th>
                <th>Gateway</th>
                <th className="num">Reserved</th>
                <th className="num">Growth %</th>
                <th className="num">Prefix</th>
                <th className="no-print" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key}>
                  <td>
                    <input
                      value={r.name}
                      onChange={(e) => update(r.key, { name: e.target.value })}
                      placeholder="Department name"
                    />
                  </td>
                  <td style={{ width: 90 }}>
                    <input
                      type="number"
                      min={1}
                      value={r.required_hosts}
                      onChange={(e) => update(r.key, { required_hosts: Number(e.target.value) })}
                    />
                  </td>
                  <td style={{ width: 80 }}>
                    <input
                      type="number"
                      min={1}
                      max={4094}
                      value={r.vlan_id}
                      onChange={(e) => update(r.key, { vlan_id: e.target.value })}
                      placeholder="—"
                    />
                  </td>
                  <td style={{ width: 150 }}>
                    <input
                      value={r.gateway}
                      onChange={(e) => update(r.key, { gateway: e.target.value })}
                      placeholder="—"
                    />
                  </td>
                  <td style={{ width: 90 }}>
                    <input
                      type="number"
                      min={0}
                      value={r.additional_reserved_addresses}
                      onChange={(e) =>
                        update(r.key, { additional_reserved_addresses: Number(e.target.value) })
                      }
                    />
                  </td>
                  <td style={{ width: 90 }}>
                    <input
                      value={r.growth_percent}
                      onChange={(e) => update(r.key, { growth_percent: e.target.value })}
                      placeholder="—"
                    />
                  </td>
                  <td style={{ width: 80 }}>
                    <input
                      value={r.prefix_length}
                      onChange={(e) => update(r.key, { prefix_length: e.target.value })}
                      placeholder="auto"
                    />
                  </td>
                  <td className="no-print" style={{ width: 40 }}>
                    <button
                      type="button"
                      className="btn subtle small"
                      title="Remove"
                      onClick={() => setRows((rs) => rs.filter((x) => x.key !== r.key))}
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <div className="empty">No departments — add at least one.</div>}
        </div>
      </div>

      {result && (
        <>
          <div className="card">
            <div className="page-head" style={{ marginBottom: 8 }}>
              <div>
                <h2 style={{ margin: 0 }}>Preview — {result.base_network}</h2>
                <div className="sub">
                  {result.allocations.length} allocation(s) · algorithm{' '}
                  {result.algorithm_version ?? '—'}
                </div>
              </div>
              <div className="action-row no-print">
                <input
                  style={{ width: 220 }}
                  value={planName}
                  onChange={(e) => setPlanName(e.target.value)}
                  placeholder="Plan name"
                />
                <input
                  style={{ width: 240 }}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Notes (optional)"
                />
                <button className="btn" disabled={busy} onClick={savePlan}>
                  Save as plan
                </button>
              </div>
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th className="num">#</th>
                    <th>Department</th>
                    <th>Network</th>
                    <th className="num">Hosts (req/effective)</th>
                    <th className="num">Usable</th>
                    <th className="num">Util %</th>
                    <th>Gateway</th>
                    <th className="num">VLAN</th>
                  </tr>
                </thead>
                <tbody>
                  {result.allocations.map((a) => (
                    <tr key={a.sequence}>
                      <td className="num">{a.sequence}</td>
                      <td>{a.department}</td>
                      <td className="mono">{a.network}</td>
                      <td className="num">
                        {a.requested_hosts} / {a.effective_hosts}
                      </td>
                      <td className="num">{a.usable_capacity}</td>
                      <td className="num">{a.utilization_percent.toFixed(1)}</td>
                      <td className="mono">{a.gateway ?? '—'}</td>
                      <td className="num">{a.vlan_id ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {Array.isArray(result.warnings) && result.warnings.length > 0 && (
              <ul className="warn-list">
                {result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}

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
                  {result.remaining_ranges.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="empty">
                        None — parent network fully allocated.
                      </td>
                    </tr>
                  ) : (
                    result.remaining_ranges.map((r, i) => (
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
        </>
      )}
    </>
  )
}
