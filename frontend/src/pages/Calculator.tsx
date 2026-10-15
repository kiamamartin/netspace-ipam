import { useState, type FormEvent } from 'react'
import { api, errorMessage, type SubnetCalcResult } from '../api'
import { ErrorBanner, PageHead } from '../ui'

type Tool = 'subnet' | 'split' | 'summarize'

interface SplitResult {
  parent: string
  parent_details: Record<string, unknown>
  count: number
  subnets: Record<string, unknown>[]
}

interface SummarizeResult {
  summary?: string
  [key: string]: unknown
}

const DETAIL_KEYS = [
  'network',
  'network_address',
  'broadcast_address',
  'netmask',
  'wildcard_mask',
  'prefix_length',
  'total_addresses',
  'usable_hosts',
  'first_usable',
  'last_usable',
  'address_range',
  'address_class',
  'address_scope',
  'required_prefix_length',
  'required_subnet_mask',
  'subnets_available',
  'requested_prefix_length',
  'requested_network',
  'binary_network',
  'binary_mask',
]

export default function Calculator() {
  const [tool, setTool] = useState<Tool>('subnet')

  // subnet tool state
  const [network, setNetwork] = useState('192.168.10.0/24')
  const [hosts, setHosts] = useState('')
  const [prefixLen, setPrefixLen] = useState('')
  const [subnetResult, setSubnetResult] = useState<SubnetCalcResult | null>(null)

  // split tool state
  const [splitNet, setSplitNet] = useState('192.168.10.0/24')
  const [splitCount, setSplitCount] = useState('4')
  const [splitPrefix, setSplitPrefix] = useState('')
  const [splitResult, setSplitResult] = useState<SplitResult | null>(null)

  // summarize tool state
  const [list, setList] = useState('192.168.10.0/26\n192.168.10.64/26\n192.168.10.128/25')
  const [sumResult, setSumResult] = useState<SummarizeResult | null>(null)

  const [error, setError] = useState<string | null>(null)

  async function runSubnet(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      const body: Record<string, unknown> = { network }
      if (hosts.trim()) body.hosts = Number(hosts)
      if (prefixLen.trim()) body.prefix_length = Number(prefixLen)
      setSubnetResult(await api.post<SubnetCalcResult>('/api/v1/calculator/subnet', body))
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function runSplit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      const body: Record<string, unknown> = { network: splitNet }
      if (splitPrefix.trim()) body.prefix_length = Number(splitPrefix)
      else body.count = Number(splitCount)
      setSplitResult(await api.post<SplitResult>('/api/v1/calculator/split', body))
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function runSummarize(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      const networks = list
        .split(/[\n,]+/)
        .map((s) => s.trim())
        .filter(Boolean)
      setSumResult(await api.post<SummarizeResult>('/api/v1/calculator/summarize', { networks }))
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <>
      <PageHead title="Subnet Calculator" sub="IPv4/IPv6 properties, splitting and summarization" />
      <div className="tabs no-print">
        {(['subnet', 'split', 'summarize'] as Tool[]).map((t) => (
          <button
            key={t}
            className={`btn subtle small${tool === t ? ' active' : ''}`}
            onClick={() => setTool(t)}
          >
            {t === 'subnet' ? 'Subnet details' : t === 'split' ? 'Split network' : 'Summarize'}
          </button>
        ))}
      </div>

      <ErrorBanner message={error} />

      {tool === 'subnet' && (
        <div className="card">
          <form className="form-grid" onSubmit={runSubnet}>
            <label className="field">
              Network / address / prefix
              <input
                value={network}
                onChange={(e) => setNetwork(e.target.value)}
                placeholder="10.0.0.0/24, 10.0.0.5 or 24"
              />
            </label>
            <label className="field">
              Required hosts (optional)
              <input
                value={hosts}
                onChange={(e) => setHosts(e.target.value)}
                placeholder="e.g. 50"
                inputMode="numeric"
              />
            </label>
            <label className="field">
              Target prefix (optional)
              <input
                value={prefixLen}
                onChange={(e) => setPrefixLen(e.target.value)}
                placeholder="e.g. 26"
                inputMode="numeric"
              />
            </label>
            <div className="form-actions" style={{ alignSelf: 'end' }}>
              <button className="btn" type="submit">
                Calculate
              </button>
            </div>
          </form>

          {subnetResult && (
            <>
              <h2>Result</h2>
              <div className="kv">
                {DETAIL_KEYS.filter(
                  (k) => subnetResult[k] !== undefined && subnetResult[k] !== null,
                ).map((k) => (
                  <div key={k}>
                    <div className="k">{k.replace(/_/g, ' ')}</div>
                    <div className="v mono">{String(subnetResult[k])}</div>
                  </div>
                ))}
              </div>
              {Array.isArray(subnetResult.warnings) && subnetResult.warnings.length > 0 && (
                <ul className="warn-list">
                  {subnetResult.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      )}

      {tool === 'split' && (
        <div className="card">
          <form className="form-grid" onSubmit={runSplit}>
            <label className="field">
              Parent network
              <input value={splitNet} onChange={(e) => setSplitNet(e.target.value)} />
            </label>
            <label className="field">
              Number of equal subnets
              <input
                value={splitCount}
                onChange={(e) => setSplitCount(e.target.value)}
                inputMode="numeric"
              />
            </label>
            <label className="field">
              Or target prefix length
              <input
                value={splitPrefix}
                onChange={(e) => setSplitPrefix(e.target.value)}
                placeholder="e.g. 26"
                inputMode="numeric"
              />
            </label>
            <div className="form-actions" style={{ alignSelf: 'end' }}>
              <button className="btn" type="submit">
                Split
              </button>
            </div>
          </form>

          {splitResult && (
            <>
              <h2>
                {splitResult.count} subnets of <span className="mono">{splitResult.parent}</span>
              </h2>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th className="num">#</th>
                      <th>Network</th>
                      <th>Range</th>
                      <th className="num">Usable hosts</th>
                    </tr>
                  </thead>
                  <tbody>
                    {splitResult.subnets.map((s, i) => (
                      <tr key={i}>
                        <td className="num">{i + 1}</td>
                        <td className="mono">{String(s.network ?? s.cidr ?? '—')}</td>
                        <td className="mono small">{String(s.address_range ?? '—')}</td>
                        <td className="num">{String(s.usable_hosts ?? '—')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {tool === 'summarize' && (
        <div className="card">
          <form className="stack" onSubmit={runSummarize}>
            <label className="field">
              Networks (one per line or comma separated)
              <textarea value={list} onChange={(e) => setList(e.target.value)} rows={6} />
            </label>
            <div className="form-actions">
              <button className="btn" type="submit">
                Summarize
              </button>
            </div>
          </form>
          {sumResult && (
            <div className="kv" style={{ marginTop: 14 }}>
              {Object.entries(sumResult).map(([k, v]) => (
                <div key={k}>
                  <div className="k">{k.replace(/_/g, ' ')}</div>
                  <div className="v mono">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  )
}
