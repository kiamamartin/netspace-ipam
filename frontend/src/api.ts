/**
 * Typed client for the NetSpace IPAM FastAPI backend.
 * All errors are normalized to `ApiError` with the backend's message.
 */

export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface ApiErrorDetail {
  field?: string
  message: string
}

export class ApiError extends Error {
  code: string
  status: number
  details: ApiErrorDetail[]
  constructor(status: number, code: string, message: string, details: ApiErrorDetail[] = []) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

export type Environment = 'production' | 'staging' | 'development' | 'lab'
export type NetworkStatus = 'active' | 'planned' | 'deprecated'
export type SubnetStatus = 'allocated' | 'reserved' | 'released'
export type IPStatus = 'assigned' | 'available' | 'reserved' | 'deprecated'
export type PlanStatus = 'draft' | 'active' | 'archived' | 'superseded'

export interface Network {
  id: number
  name: string
  cidr: string
  family: number
  description: string | null
  environment: Environment
  site: string | null
  status: NetworkStatus
  created_at: string
  updated_at: string
}

export interface Subnet {
  id: number
  network_id: number
  name: string
  cidr: string
  family: number
  prefix_length: number
  vlan_id: number | null
  gateway: string | null
  status: SubnetStatus
  description: string | null
  details: Record<string, unknown>
  ip_address_count: number
  created_at: string
  updated_at: string
}

export interface NetworkDetail extends Network {
  details: Record<string, unknown>
  subnets: Subnet[]
}

export interface IPAddress {
  id: number
  subnet_id: number
  address: string
  family: number
  hostname: string | null
  device: string | null
  department_id: number | null
  status: IPStatus
  description: string | null
  created_at: string
  updated_at: string
}

export interface Department {
  id: number
  name: string
  description: string | null
  default_host_requirement: number
  vlan_id: number | null
  site: string | null
  created_at: string
  updated_at: string
}

export interface PlanListItem {
  id: number
  name: string
  base_network: string
  family: number
  algorithm_version: string
  status: PlanStatus
  department_count: number
  overall_utilization_percent: number
  created_at: string
  updated_at: string
}

export interface AllocationRow {
  sequence: number
  department: string
  department_id?: number | null
  network: string
  prefix_length: number
  vlan_id?: number | null
  requested_hosts: number
  effective_hosts: number
  total_addresses: number
  usable_capacity: number
  unused_usable_capacity: number
  utilization_percent: number
  space_utilization_percent: number
  gateway: string | null
  reserved_addresses: number
  status: string
  growth_percent: number
  network_address?: string
  first_usable?: string
  last_usable?: string
  address_range?: string
  subnet_mask?: string | null
  wildcard_mask?: string | null
  broadcast_address?: string | null
}

export interface RemainingRange {
  start: string
  end: string
  total_addresses: number
  usable_hosts: number
}

export interface VlsmResult {
  base_network: string
  family: number
  allocations: AllocationRow[]
  remaining_ranges: RemainingRange[]
  summary: Record<string, unknown>
  warnings?: string[]
  algorithm_version?: string
}

export interface Plan {
  id: number
  name: string
  base_network: string
  family: number
  algorithm_version: string
  status: PlanStatus
  inputs: {
    base_network: string
    family: number
    policy: Record<string, unknown>
    departments: Record<string, unknown>[]
  }
  results: VlsmResult
  notes: string | null
  created_at: string
  updated_at: string
}

export interface NetworkUtilization {
  network_id: number
  name: string
  cidr: string
  allocated_addresses: number
  total_addresses: number
  utilization_percent: number
  subnet_count: number
}

export interface DashboardSummary {
  total_networks: number
  total_subnets: number
  total_ip_addresses: number
  ip_available: number
  ip_reserved: number
  ip_assigned: number
  ip_deprecated: number
  total_plans: number
  active_plans: number
  average_utilization_percent: number
  networks: NetworkUtilization[]
  conflicts: Record<string, unknown>[]
  near_capacity: NetworkUtilization[]
  recent_activity: Record<string, unknown>[]
}

export interface AuditEvent {
  id: number
  resource_type: string
  resource_id: string
  action: string
  timestamp: string
  actor: string | null
  summary: string | null
}

export interface SubnetCalcResult {
  network?: string
  warnings: string[]
  [key: string]: unknown
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
    ...init,
  })
  if (!res.ok) {
    let code = 'error'
    let message = `Request failed (${res.status})`
    let details: ApiErrorDetail[] = []
    try {
      const body = await res.json()
      if (body?.error) {
        code = body.error.code ?? code
        message = body.error.message ?? message
        details = body.error.details ?? []
      }
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, code, message, details)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}

/** Trigger a browser download for a report export. */
export function download(path: string): void {
  const a = document.createElement('a')
  a.href = path
  a.download = ''
  document.body.appendChild(a)
  a.click()
  a.remove()
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const extra = err.details.map((d) => (d.field ? `${d.field}: ${d.message}` : d.message)).join('; ')
    return extra ? `${err.message} — ${extra}` : err.message
  }
  if (err instanceof Error) return err.message
  return String(err)
}
