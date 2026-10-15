import type { ReactNode } from 'react'
import { download } from './api'

export function PageHead({ title, sub, actions }: { title: string; sub?: string; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {sub ? <div className="sub">{sub}</div> : null}
      </div>
      {actions ? <div className="action-row">{actions}</div> : null}
    </div>
  )
}

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null
  return <div className="banner error">{message}</div>
}

export function SuccessBanner({ message }: { message: string | null }) {
  if (!message) return null
  return <div className="banner success">{message}</div>
}

const STATUS_CLASS: Record<string, string> = {
  active: 'ok',
  allocated: 'ok',
  assigned: 'ok',
  draft: '',
  reserved: 'warn',
  planned: 'warn',
  available: 'neutral',
  released: 'neutral',
  archived: 'neutral',
  superseded: 'neutral',
  deprecated: 'danger',
}

export function Badge({ status }: { status: string }) {
  return <span className={`badge ${STATUS_CLASS[status] ?? 'neutral'}`}>{status}</span>
}

export function Meter({ percent, hot = false }: { percent: number; hot?: boolean }) {
  const pct = Math.max(0, Math.min(100, percent))
  return (
    <div className={`meter${hot ? ' hot' : ''}`} title={`${pct.toFixed(1)}%`}>
      <span style={{ width: `${pct}%` }} />
    </div>
  )
}

export function Pagination({
  page,
  pages,
  total,
  onChange,
}: {
  page: number
  pages: number
  total: number
  onChange: (page: number) => void
}) {
  if (total === 0) return null
  return (
    <div className="pager no-print">
      <button className="btn subtle small" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        ← Prev
      </button>
      <span className="muted">
        Page {page} of {Math.max(pages, 1)} · {total} total
      </span>
      <button className="btn subtle small" disabled={page >= pages} onClick={() => onChange(page + 1)}>
        Next →
      </button>
    </div>
  )
}

/** CSV / Excel / PDF export buttons for a report endpoint prefix. */
export function ExportButtons({ base }: { base: string }) {
  return (
    <div className="action-row no-print">
      <button className="btn subtle small" onClick={() => download(`${base}/csv`)}>
        Export CSV
      </button>
      <button className="btn subtle small" onClick={() => download(`${base}/xlsx`)}>
        Export Excel
      </button>
      <button className="btn subtle small" onClick={() => download(`${base}/pdf`)}>
        Export PDF
      </button>
      <button className="btn ghost small" onClick={() => window.print()}>
        Print
      </button>
    </div>
  )
}
