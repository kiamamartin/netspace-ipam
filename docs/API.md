# NetSpace IPAM — API reference

Base prefix: `/api/v1` · Interactive docs: `/docs` (Swagger) ·
Errors: `{"error": {"code", "message", "details": [{"field", "message"}]}}`

> This file documents the **implemented v1 API**. Target automation endpoints
> are specified in [ARCHITECTURE.md](ARCHITECTURE.md) Part II and are added here
> as each milestone lands. Do not treat the Part II surface as available.

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
| GET/POST | `/subnets` | List (`q`, `network_id`, `status`, `owner`, `site`, paging; rows include `ip_address_count` + `utilization`) / allocate (422 misaligned, 409 overlap/duplicate) |
| GET/PATCH/DELETE | `/subnets/{id}` | Detail (includes utilization) / update (move, owner, location, state; revalidate) / delete |
| POST | `/subnets/{id}/reserve` | Reserve a subnet (409 invalid lifecycle transition) |
| POST | `/subnets/{id}/release` | Release a subnet; `?force=true` when addresses still exist (409 `subnet_not_empty`) |
| GET | `/subnets/{id}/history` | Audit/event history for the subnet (newest first) |
| GET/POST | `/ip-addresses` | List (`q`, `status`, `subnet_id`, `department_id`, paging) / register address |
| GET/PATCH/DELETE | `/ip-addresses/{id}` | Detail / update / delete |
| POST | `/ip-addresses/{id}/reserve` | Reserve an available address (409 invalid lifecycle transition) |
| POST | `/ip-addresses/{id}/release` | Release a reserved address (row removed, history retained) |
| GET | `/ip-addresses/{id}/history` | Audit/event history for the address (newest first) |
| GET/POST | `/departments` | List / create |
| GET/PATCH/DELETE | `/departments/{id}` | Detail / update / delete |

## Authentication and user administration

| Method | Path | Description |
| --- | --- | --- |
| POST | `/auth/login` | Exchange username/password for a bearer token (rate limited) |
| GET | `/auth/me` | Current authenticated identity |
| GET/POST | `/auth/users` | List / create users (admin only) |
| PATCH/DELETE | `/auth/users/{id}` | Update role/password/active flag / delete (admin only) |

## Allocation plans

| Method | Path | Description |
| --- | --- | --- |
| GET/POST | `/allocation-plans` | List / save a plan (validated, nothing committed) |
| GET/PATCH | `/allocation-plans/{id}` | Full plan (inputs + results) / notes & name |
| POST | `/allocation-plans/{id}/activate` | Transactionally commit the plan to inventory |
| POST | `/allocation-plans/{id}/recalculate` | Recompute from stored inputs |
| POST | `/allocation-plans/{id}/archive` | Archive an eligible plan |

## Reports

Export endpoints require authentication (`Authorization: Bearer ...`); an
anonymous request receives `401` before the resource is resolved (no
enumeration).

| Method | Path | Description |
| --- | --- | --- |
| GET | `/reports/networks/{id}/csv` \| `xlsx` \| `pdf` | Network report export |
| GET | `/reports/allocation-plans/{id}/csv` \| `xlsx` \| `pdf` | Plan export |

## Dashboard & audit

| Method | Path | Description |
| --- | --- | --- |
| GET | `/dashboard/summary` | Counts, utilization, conflicts, near-capacity, recent activity (authenticated roles) |
| GET | `/audit-events` | Paginated audit log (`resource_type`, `action` filters) |

## Status codes

- `200/201` success · `401` unauthenticated · `403` forbidden role · `404` not
  found · `409` conflicts (overlap, duplicate name, plan conflicts, network not
  empty, invalid lifecycle transition) · `422` validation (host bits set,
  misaligned, family mismatch, VLSM requirement errors) · `429` login rate limit
  · `413` request body too large · `500` never exposes internals.
