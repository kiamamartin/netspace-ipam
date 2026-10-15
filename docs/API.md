# NetSpace IPAM — API reference

Base prefix: `/api/v1` · Interactive docs: `/docs` (Swagger) ·
Errors: `{"error": {"code", "message", "details": [{"field", "message"}]}}`

## Health

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Liveness + algorithm version |

## Calculator (stateless)

| Method | Path | Description |
| --- | --- | --- |
| POST | `/calculator/subnet` | Subnet properties for a CIDR/address/prefix; optional `hosts` / `prefix_length` |
| POST | `/calculator/vlsm` | Run a VLSM allocation (preview only, nothing stored) |
| POST | `/calculator/split` | Split a network into `count` equal subnets or a target prefix |
| POST | `/calculator/summarize` | Summarize a list of networks into aggregates |
| POST | `/calculator/validate` | Validate CIDR / VLAN / gateway / full department set without allocating |

## Inventory

| Method | Path | Description |
| --- | --- | --- |
| GET/POST | `/networks` | List (`q`, `family`, `environment`, `status`, `sort`, paging) / create |
| GET/PATCH/DELETE | `/networks/{id}` | Detail (with computed properties + subnets) / update / delete (409 if not empty) |
| GET/POST | `/subnets` | List (filters) / allocate (422 misaligned, 409 overlap/duplicate) |
| GET/PATCH/DELETE | `/subnets/{id}` | Detail / update (move, revalidate) / release or delete |
| GET/POST | `/ip-addresses` | List (`q`, `status`, `subnet_id`) / register address |
| GET/PATCH/DELETE | `/ip-addresses/{id}` | Detail / update / release |
| GET/POST | `/departments` | List / create |
| GET/PATCH/DELETE | `/departments/{id}` | Detail / update / delete |

## Allocation plans

| Method | Path | Description |
| --- | --- | --- |
| GET/POST | `/allocation-plans` | List / save a plan (validated, nothing committed) |
| GET/PATCH | `/allocation-plans/{id}` | Full plan (inputs + results) / notes & name |
| POST | `/allocation-plans/{id}/activate` | Transactionally commit the plan to inventory |
| POST | `/allocation-plans/{id}/recalculate` | Recompute from stored inputs |
| POST | `/allocation-plans/{id}/archive` | Archive an eligible plan |

## Reports

| Method | Path | Description |
| --- | --- | --- |
| GET | `/reports/networks/{id}/csv` \| `xlsx` \| `pdf` | Network report export |
| GET | `/reports/allocation-plans/{id}/csv` \| `xlsx` \| `pdf` | Plan export |

## Dashboard & audit

| Method | Path | Description |
| --- | --- | --- |
| GET | `/dashboard/summary` | Counts, utilization, conflicts, near-capacity, activity |
| GET | `/audit-events` | Paginated audit log (`resource_type`, `action` filters) |

## Status codes

- `200/201` success · `404` not found · `409` conflicts (overlap, duplicate name,
  plan conflicts, network not empty) · `422` validation (host bits set,
  misaligned, family mismatch, VLSM requirement errors) · `500` never exposes
  internals.
