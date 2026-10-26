import { useState, type FormEvent } from 'react'
import { Tabs } from '@ark-ui/react/tabs'
import { api, errorMessage, type SubnetCalcResult } from '../api'
import { ErrorBanner, Icon, PageHead, TextField } from '../ui'

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
  const [busy, setBusy] = useState(false)

  async function runSubnet(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const body: Record<string, unknown> = { network }
      if (hosts.trim()) body.hosts = Number(hosts)
      if (prefixLen.trim()) body.prefix_length = Number(prefixLen)
      setSubnetResult(await api.post<SubnetCalcResult>('/api/v1/calculator/subnet', body))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function runSplit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const body: Record<string, unknown> = { network: splitNet }
      if (splitPrefix.trim()) body.prefix_length = Number(splitPrefix)
      else body.count = Number(splitCount)
      setSplitResult(await api.post<SplitResult>('/api/v1/calculator/split', body))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function runSummarize(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const networks = list
        .split(/[\n,]+/)
        .map((s) => s.trim())
        .filter(Boolean)
      setSumResult(await api.post<SummarizeResult>('/api/v1/calculator/summarize', { networks }))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHead title="Subnet Calculator" sub="IPv4/IPv6 properties, splitting and summarization" />
      <Tabs.Root
        value={tool}
        onValueChange={(details) => setTool(details.value as Tool)}
        lazyMount
        unmountOnExit
      >
        <Tabs.List className="no-print">
          <Tabs.Trigger value="subnet">
            <Icon name="calculator" size={13} /> Subnet details
          </Tabs.Trigger>
          <Tabs.Trigger value="split">
            <Icon name="planner" size={13} /> Split network
          </Tabs.Trigger>
          <Tabs.Trigger value="summarize">
            <Icon name="network" size={13} /> Summarize
          </Tabs.Trigger>
          <Tabs.Indicator />
        </Tabs.List>

        <ErrorBanner message={error} />

        <Tabs.Content value="subnet">
          <div className="card">
            <form className="form-grid" onSubmit={runSubnet}>
              <TextField
                label="Network / address / prefix"
                value={network}
                onChange={setNetwork}
                placeholder="10.0.0.0/24, 10.0.0.5 or 24"
                mono
              />
              <TextField
                label="Required hosts (optional)"
                value={hosts}
                onChange={setHosts}
                placeholder="e.g. 50"
                inputMode="numeric"
              />
              <TextField
                label="Target prefix (optional)"
                value={prefixLen}
                onChange={setPrefixLen}
                placeholder="e.g. 26"
                inputMode="numeric"
              />
              <div className="form-actions" style={{ alignSelf: 'end' }}>
                <button className="btn" type="submit" disabled={busy}>
                  {busy ? 'Calculating…' : 'Calculate'}
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
        </Tabs.Content>

        <Tabs.Content value="split">
          <div className="card">
            <form className="form-grid" onSubmit={runSplit}>
              <TextField label="Parent network" value={splitNet} onChange={setSplitNet} mono />
              <TextField
                label="Number of equal subnets"
                value={splitCount}
                onChange={setSplitCount}
                inputMode="numeric"
              />
              <TextField
                label="Or target prefix length"
                value={splitPrefix}
                onChange={setSplitPrefix}
                placeholder="e.g. 26"
                inputMode="numeric"
              />
              <div className="form-actions" style={{ alignSelf: 'end' }}>
                <button className="btn" type="submit" disabled={busy}>
                  {busy ? 'Splitting…' : 'Split'}
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
        </Tabs.Content>

        <Tabs.Content value="summarize">
          <div className="card">
            <form className="stack" onSubmit={runSummarize}>
              <label className="field">
                Networks (one per line or comma separated)
                <textarea value={list} onChange={(e) => setList(e.target.value)} rows={6} />
              </label>
              <div className="form-actions">
                <button className="btn" type="submit" disabled={busy}>
                  {busy ? 'Summarizing…' : 'Summarize'}
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
        </Tabs.Content>
      </Tabs.Root>
    </>
  )
}
