import type { ReactNode } from 'react'

/** Render a single key/value pair for the `.kv` grid layout. */
export function kv(label: string, value: ReactNode) {
  return (
    <div>
      <div className="k">{label}</div>
      <div className="v">{value}</div>
    </div>
  )
}
