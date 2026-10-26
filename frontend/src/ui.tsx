import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from 'react'
import { Clipboard } from '@ark-ui/react/clipboard'
import { Dialog } from '@ark-ui/react/dialog'
import { Field } from '@ark-ui/react/field'
import { Menu } from '@ark-ui/react/menu'
import { NumberInput } from '@ark-ui/react/number-input'
import { Pagination } from '@ark-ui/react/pagination'
import { Progress } from '@ark-ui/react/progress'
import { Select, createListCollection } from '@ark-ui/react/select'
import { Toast, Toaster } from '@ark-ui/react/toast'
import { Tooltip } from '@ark-ui/react/tooltip'
import { download } from './api'
import { setConfirmHandler, toaster, type ConfirmOptions } from './feedback'
import { toggleTheme, useTheme } from './theme'

/* ================================================================== *
 * Icons — minimal inline SVG set (stroke based, 24×24 grid)
 * ================================================================== */

const ICONS: Record<string, ReactNode> = {
  dashboard: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
    </>
  ),
  calculator: (
    <>
      <rect x="4" y="2" width="16" height="20" rx="2" />
      <path d="M8 6h8M8 11h.01M12 11h.01M16 11h.01M8 15h.01M12 15h.01M16 15h.01M8 19h.01M12 19h.01M16 19h.01" />
    </>
  ),
  planner: (
    <>
      <path d="M3 4v6a2 2 0 0 0 2 2h7" />
      <path d="M3 20v-4a2 2 0 0 1 2-2h7" />
      <path d="m16 8 4 4-4 4" />
      <circle cx="15" cy="4" r="2" />
      <circle cx="15" cy="20" r="2" />
    </>
  ),
  plans: (
    <>
      <path d="M9 4H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2" />
      <rect x="9" y="2" width="6" height="4" rx="1" />
      <path d="M9 12h6M9 16h4" />
    </>
  ),
  network: (
    <>
      <circle cx="12" cy="5" r="2.5" />
      <circle cx="5" cy="19" r="2.5" />
      <circle cx="19" cy="19" r="2.5" />
      <path d="M12 7.5v4m0 0-5.5 5m5.5-5 5.5 5" />
    </>
  ),
  ip: <path d="M9 3 7 21M17 3l-2 18M4 9h16M3 15h16" />,
  users: (
    <>
      <path d="M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2" />
      <circle cx="9.5" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87M17 3.13a4 4 0 0 1 0 7.75" />
    </>
  ),
  print: (
    <>
      <path d="M6 9V3h12v6" />
      <path d="M6 18H4a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2" />
      <rect x="6" y="14" width="12" height="8" rx="1" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </>
  ),
  chevronDown: <path d="m6 9 6 6 6-6" />,
  chevronLeft: <path d="m15 18-6-6 6-6" />,
  chevronRight: <path d="m9 18 6-6-6-6" />,
  more: (
    <>
      <circle cx="12" cy="5" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="12" cy="19" r="1.4" fill="currentColor" stroke="none" />
    </>
  ),
  edit: <path d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />,
  trash: <path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m3 0-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6" />,
  check: <path d="m4 12.5 5 5L20 6.5" />,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  alert: (
    <>
      <path d="M12 3 2.5 20h19L12 3Z" />
      <path d="M12 9.5v4.5M12 17.2h.01" />
    </>
  ),
  copy: (
    <>
      <rect x="9" y="9" width="12" height="12" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </>
  ),
  refresh: <path d="M21 12a9 9 0 1 1-2.64-6.36M21 3v6h-6" />,
  download: <path d="M12 3v12m0 0 4-4m-4 4-4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />,
  power: <path d="M12 3v9M6.3 6.3a8 8 0 1 0 11.4 0" />,
  archive: (
    <>
      <rect x="3" y="4" width="18" height="4" rx="1" />
      <path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8M10 12h4" />
    </>
  ),
  save: <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2zM17 21v-8H7v8M7 3v5h8" />,
  eye: (
    <>
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  server: (
    <>
      <rect x="2" y="3" width="20" height="7" rx="2" />
      <rect x="2" y="14" width="20" height="7" rx="2" />
      <path d="M6 6.5h.01M6 17.5h.01" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </>
  ),
  moon: <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />,
}

export type IconName = keyof typeof ICONS

export function Icon({
  name,
  size = 16,
  style,
}: {
  name: IconName
  size?: number
  style?: CSSProperties
}) {
  return (
    <svg
      width={size}
      height={size}
      style={style}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {ICONS[name]}
    </svg>
  )
}

/* ================================================================== *
 * Toast host
 * ================================================================== */

const TOAST_ICON: Record<string, string> = { success: '\u2713', error: '\u2715', warning: '!', info: 'i' }

export function ToastHost() {
  return (
    <Toaster toaster={toaster}>
      {(toast) => (
        <Toast.Root data-type={toast.type ?? 'info'}>
          <span className="toast-icon">{TOAST_ICON[toast.type ?? 'info'] ?? 'i'}</span>
          <div className="toast-body">
            {toast.title ? <Toast.Title>{toast.title}</Toast.Title> : null}
            {toast.description ? <Toast.Description>{toast.description}</Toast.Description> : null}
          </div>
          <Toast.CloseTrigger onClick={() => toaster.dismiss(toast.id)} aria-label="Dismiss notification">
            <Icon name="x" size={13} />
          </Toast.CloseTrigger>
        </Toast.Root>
      )}
    </Toaster>
  )
}

/* ================================================================== *
 * Confirm (alert dialog) — promise based, drop-in for window.confirm
 * ================================================================== */

export function ConfirmHost() {
  const [request, setRequest] = useState<{ opts: ConfirmOptions; resolve: (v: boolean) => void } | null>(null)

  useEffect(() => {
    setConfirmHandler((opts) => new Promise<boolean>((resolve) => setRequest({ opts, resolve })))
    return () => {
      setConfirmHandler(null)
    }
  }, [])

  const close = (result: boolean) => {
    request?.resolve(result)
    setRequest(null)
  }

  const opts = request?.opts

  return (
    <Dialog.Root
      role="alertdialog"
      open={request != null}
      onOpenChange={(e) => {
        if (!e.open) close(false)
      }}
      lazyMount
      unmountOnExit
    >
      <Dialog.Backdrop />
      <Dialog.Positioner>
        <Dialog.Content>
          {opts?.danger !== false && (
            <div className="dialog-alert-icon">
              <Icon name="alert" size={20} />
            </div>
          )}
          <div className={opts?.danger === false ? 'dialog-header' : 'dialog-alert-body'}>
            <div>
              <Dialog.Title>{opts?.title ?? ''}</Dialog.Title>
              {opts?.description && <Dialog.Description>{opts.description}</Dialog.Description>}
            </div>
          </div>
          <div className="dialog-footer">
            <button className="btn subtle" onClick={() => close(false)}>
              {opts?.cancelLabel ?? 'Cancel'}
            </button>
            <button
              className={opts?.danger === false ? 'btn' : 'btn danger'}
              autoFocus
              onClick={() => close(true)}
            >
              {opts?.confirmLabel ?? 'Confirm'}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  )
}

/* ================================================================== *
 * Modal — Ark Dialog wrapper for forms & panels
 * ================================================================== */

export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  wide = false,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  children: ReactNode
  footer?: ReactNode
  wide?: boolean
}) {
  return (
    <Dialog.Root open={open} onOpenChange={(e) => onOpenChange(e.open)} lazyMount unmountOnExit>
      <Dialog.Backdrop />
      <Dialog.Positioner>
        <Dialog.Content style={wide ? { width: 'min(94vw, 660px)' } : undefined}>
          <div className="dialog-header">
            <Dialog.Title>{title}</Dialog.Title>
            {description && <Dialog.Description>{description}</Dialog.Description>}
          </div>
          <div className="dialog-body">{children}</div>
          {footer && <div className="dialog-footer">{footer}</div>}
          <Dialog.CloseTrigger aria-label="Close dialog">
            <Icon name="x" size={15} />
          </Dialog.CloseTrigger>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  )
}

/* ================================================================== *
 * Form fields
 * ================================================================== */

export function TextField({
  label,
  value,
  onChange,
  required,
  placeholder,
  type = 'text',
  inputMode,
  mono = false,
  span = false,
  disabled = false,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  required?: boolean
  placeholder?: string
  type?: string
  inputMode?: 'numeric' | 'decimal' | 'text'
  mono?: boolean
  span?: boolean
  disabled?: boolean
}) {
  return (
    <Field.Root required={required} disabled={disabled} style={span ? { gridColumn: '1 / -1' } : undefined}>
      <Field.Label>
        {label}
        {required ? <Field.RequiredIndicator> *</Field.RequiredIndicator> : null}
      </Field.Label>
      <Field.Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        type={type}
        inputMode={inputMode}
        className={mono ? 'mono' : undefined}
      />
    </Field.Root>
  )
}

export function SelectField({
  label,
  value,
  onChange,
  options,
  placeholder = 'Select…',
  span = false,
  hideLabel = false,
  required = false,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string }[]
  placeholder?: string
  span?: boolean
  hideLabel?: boolean
  required?: boolean
}) {
  const collection = useMemo(() => createListCollection({ items: options }), [options])
  return (
    <Select.Root
      collection={collection}
      value={value ? [value] : []}
      onValueChange={(details) => onChange(details.value[0] ?? '')}
      positioning={{ sameWidth: true }}
      required={required}
    >
      <div style={span ? { gridColumn: '1 / -1' } : undefined}>
        {!hideLabel && (
          <div data-scope="select" data-part="label" style={{ fontSize: 12, color: 'var(--ink-soft)', fontWeight: 600, marginBottom: 5 }}>
            {label}
          </div>
        )}
        <Select.Control>
          <Select.Trigger aria-label={label}>
            <Select.ValueText placeholder={placeholder} />
            <Select.Indicator>
              <Icon name="chevronDown" size={14} />
            </Select.Indicator>
          </Select.Trigger>
        </Select.Control>
      </div>
      <Select.Positioner>
        <Select.Content>
          {collection.items.map((opt) => (
            <Select.Item key={opt.value} item={opt}>
              <Select.ItemText>{opt.label}</Select.ItemText>
              <Select.ItemIndicator>
                <Icon name="check" size={13} />
              </Select.ItemIndicator>
            </Select.Item>
          ))}
        </Select.Content>
      </Select.Positioner>
    </Select.Root>
  )
}

export function NumberField({
  value,
  onChange,
  min,
  max,
  placeholder,
  width,
}: {
  value: string | number
  onChange: (value: number) => void
  min?: number
  max?: number
  placeholder?: string
  width?: number
}) {
  return (
    <NumberInput.Root
      value={String(value ?? '')}
      onValueChange={(details) => onChange(Number.isNaN(details.valueAsNumber) ? 0 : details.valueAsNumber)}
      min={min}
      max={max}
      clampValueOnBlur
      style={width ? { width } : undefined}
    >
      <NumberInput.Control>
        <NumberInput.Input placeholder={placeholder} />
        <NumberInput.IncrementTrigger aria-label="Increase">
          <Icon name="chevronDown" size={9} style={{ transform: 'rotate(180deg)' }} />
        </NumberInput.IncrementTrigger>
        <NumberInput.DecrementTrigger aria-label="Decrease">
          <Icon name="chevronDown" size={9} />
        </NumberInput.DecrementTrigger>
      </NumberInput.Control>
    </NumberInput.Root>
  )
}

/* ================================================================== *
 * Progress meter
 * ================================================================== */

export function Meter({ percent, hot = false }: { percent: number; hot?: boolean }) {
  const pct = Math.max(0, Math.min(100, percent))
  return (
    <Progress.Root value={pct} max={100} aria-label="Utilization" style={{ minWidth: 60 }}>
      <Progress.Track className="meter">
        <Progress.Range style={{ width: `${pct}%` }} data-hot={hot || undefined} />
      </Progress.Track>
    </Progress.Root>
  )
}

/* ================================================================== *
 * Pagination (backend paginated: pages + total)
 * ================================================================== */

/** Page numbers to render around the current page, with gap markers. */
function pageWindow(page: number, pages: number): (number | 'gap')[] {
  if (pages <= 7) return Array.from({ length: pages }, (_, i) => i + 1)
  const items: (number | 'gap')[] = [1]
  const start = Math.max(2, page - 1)
  const end = Math.min(pages - 1, page + 1)
  if (start > 2) items.push('gap')
  for (let i = start; i <= end; i++) items.push(i)
  if (end < pages - 1) items.push('gap')
  items.push(pages)
  return items
}

export function PaginationBar({
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
      <Pagination.Root
        page={page}
        pageSize={1}
        count={Math.max(pages, 1)}
        siblingCount={1}
        onPageChange={(details) => onChange(details.page)}
      >
        <Pagination.PrevTrigger aria-label="Previous page">
          <Icon name="chevronLeft" size={13} />
        </Pagination.PrevTrigger>
        {pageWindow(page, Math.max(pages, 1)).map((item, i) =>
          typeof item === 'number' ? (
            <Pagination.Item key={item} type="page" value={item} aria-label={`Page ${item}`}>
              {item}
            </Pagination.Item>
          ) : (
            <Pagination.Ellipsis key={`gap-${i}`} index={i}>
              …
            </Pagination.Ellipsis>
          ),
        )}
        <Pagination.NextTrigger aria-label="Next page">
          <Icon name="chevronRight" size={13} />
        </Pagination.NextTrigger>
      </Pagination.Root>
      <span className="muted small">
        Page {page} of {Math.max(pages, 1)} · {total} total
      </span>
    </div>
  )
}

/* ================================================================== *
 * Row action menu
 * ================================================================== */

export interface RowAction {
  label: string
  icon: IconName
  danger?: boolean
  disabled?: boolean
  onSelect: () => void
}

export function RowMenu({ actions, label = 'Row actions' }: { actions: RowAction[]; label?: string }) {
  return (
    <Menu.Root>
      <Menu.Trigger asChild>
        <button className="btn subtle small icon" aria-label={label}>
          <Icon name="more" size={14} />
        </button>
      </Menu.Trigger>
      <Menu.Positioner>
        <Menu.Content>
          {actions.map((a) => (
            <Menu.Item
              key={a.label}
              value={a.label}
              className={a.danger ? 'danger-item' : undefined}
              disabled={a.disabled}
              onClick={a.onSelect}
            >
              <Icon name={a.icon} size={14} />
              {a.label}
            </Menu.Item>
          ))}
        </Menu.Content>
      </Menu.Positioner>
    </Menu.Root>
  )
}

/* ================================================================== *
 * Tooltip + copy-to-clipboard helpers
 * ================================================================== */

export function Tip({ content, children }: { content: string; children: ReactNode }) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
      <Tooltip.Positioner>
        <Tooltip.Content>{content}</Tooltip.Content>
      </Tooltip.Positioner>
    </Tooltip.Root>
  )
}

/** Mono value with a one-click copy button (Ark Clipboard). */
export function CopyValue({ value, className }: { value: string; className?: string }) {
  return (
    <Clipboard.Root value={value} className={`inline-copy ${className ?? ''}`}>
      <Clipboard.Control>
        <Clipboard.Input readOnly className="mono" />
        <Clipboard.Trigger aria-label="Copy to clipboard">
          <Clipboard.Indicator>
            <Icon name="check" size={12} />
          </Clipboard.Indicator>
          <Clipboard.Indicator copied={false}>
            <Icon name="copy" size={12} />
          </Clipboard.Indicator>
        </Clipboard.Trigger>
      </Clipboard.Control>
    </Clipboard.Root>
  )
}

/* ================================================================== *
 * Page furniture
 * ================================================================== */

/** Light/dark toggle for the topbar (persists via src/theme.ts). */
export function ThemeToggle() {
  const theme = useTheme()
  return (
    <Tip content={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
      <button
        className="btn subtle small icon"
        aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        onClick={() => toggleTheme()}
      >
        <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={14} />
      </button>
    </Tip>
  )
}

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

export function Stat({
  label,
  value,
  hint,
  dotColor,
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  dotColor?: string
}) {
  return (
    <div className="stat">
      <div className="label">
        {dotColor && <span className="dot" style={{ background: dotColor }} />}
        {label}
      </div>
      <div className="value">{value}</div>
      {hint && <div className="hint">{hint}</div>}
    </div>
  )
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="loading-note">
      <span className="spinner" /> {label}
    </div>
  )
}

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <div className="banner error" role="alert">
      {message}
    </div>
  )
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

/** CSV / Excel / PDF export buttons for a report endpoint prefix. */
export function ExportButtons({ base }: { base: string }) {
  return (
    <div className="action-row no-print">
      <button className="btn subtle small" onClick={() => download(`${base}/csv`)}>
        <Icon name="download" size={13} /> CSV
      </button>
      <button className="btn subtle small" onClick={() => download(`${base}/xlsx`)}>
        <Icon name="download" size={13} /> Excel
      </button>
      <button className="btn subtle small" onClick={() => download(`${base}/pdf`)}>
        <Icon name="download" size={13} /> PDF
      </button>
      <button className="btn ghost small" onClick={() => window.print()} aria-label="Print view">
        <Icon name="print" size={13} /> Print
      </button>
    </div>
  )
}
