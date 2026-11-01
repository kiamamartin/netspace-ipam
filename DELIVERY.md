# NetSpace IPAM — Delivery Report

Date: 2026-11-01 · Algorithm version: `vlsm-1.0.0`

Delivered scope: M0–M7. M8–M10 remain in progress.

## What was delivered

| Area | Delivered |
| --- | --- |
| Calculation engine | IPv4/IPv6 subnet math, VLSM allocator, split/summarize, structural checks |
| API | FastAPI `/api/v1`: calculator, networks, subnets, IPs, departments, plans, reports, dashboard, audit |
| Persistence | SQLAlchemy models + Alembic migrations (upgrade/downgrade verified by tests), SQLite default, any SQLAlchemy URL via `NETSPACE_DATABASE_URL` |
| Plans | Draft → activate (transactional) → recalculate → archive lifecycle with conflict detection |
| Authentication | Bearer-token login, viewer/operator/admin matrix, admin user CRUD, login rate limiting, request-size guard |
| Frontend | React 19 + TS (Vite): Dashboard, Calculator, VLSM Planner, Plans, Networks, IP Addresses, Departments, Users; responsive shell, light/dark theme, print styles |
| Inventory lifecycle | Subnet/IP reservation and release, owner/location tracking, utilization and remaining capacity, per-resource audit history |
| Reports | CSV (metadata preamble), XLSX (4 sheets), PDF (uncompressed streams, greppable) + print stylesheet |
| Ops | Dockerfiles (backend, frontend/nginx), `docker-compose.yml`, `.env.example`, docs, headless UI smoke suite |

## Acceptance criteria

### Mandatory VLSM scenario — `192.168.10.0/24`

Verified live via `POST /api/v1/calculator/vlsm` (also pinned by
`backend/tests/test_vlsm_allocator.py` and API tests):

| # | Department | Requirement | Allocation | Usable |
| --- | --- | --- | --- | --- |
| 1 | Administration | 50 hosts | `192.168.10.0/26` | 62 |
| 2 | ICT | 25 hosts | `192.168.10.64/27` | 30 |
| 3 | Finance | 20 hosts | `192.168.10.96/27` | 30 |
| 4 | Human Resources | 12 hosts | `192.168.10.128/28` | 14 |
| 5 | Guest Network | 10 hosts | `192.168.10.144/28` | 14 |
| — | Remaining | — | `192.168.10.160 – .255` | 96 |

### Allocation invariants (`backend/tests/test_invariants.py`)

1. Every allocation is contained in the parent ✔
2. No two allocations overlap ✔
3. Every allocation is prefix-aligned ✔
4. Usable capacity ≥ effective requirement (hosts + growth + reservations + gateway) ✔
5. Total allocated ≤ parent size; remaining ranges sum exactly to the remainder ✔
6. Determinism: identical input ⇒ identical output ✔

Property tests run 300 random IPv4 + 50 random IPv6 allocations and 100
growth/reservation/gateway scenarios against these invariants.

### Authentication and authorization (M5)

- `POST /api/v1/auth/login` issues a signed bearer token; `/auth/me` resolves the
  authoritative identity.
- Roles: `viewer` (read), `operator` (inventory/planning writes), `admin`
  (users, audit events, all writes). Anonymous writes receive `401`; forbidden
  role actions receive `403` server-side.
- Admin-only user lifecycle with audit events on create/update/delete; the last
  admin and self-deactivation/self-demotion are protected.
- Login attempts are limited (5 per 60 s per client IP); request bodies above
  1 MiB are rejected with `413`.
- The enterprise seed creates or updates `admin`, `operator` and `viewer`
  accounts from `NETSPACE_SEED_*_PASSWORD` environment variables; no passwords
  are stored in the repository.

### Inventory lifecycle and governance (M7)

- Parent networks contain aligned, non-overlapping subnets with owner, location,
  purpose, VLAN and lifecycle status.
- Subnet and IP reservation/release workflows enforce valid transitions and
  reject conflicting/duplicate allocations; forced subnet release is explicit.
- Utilization, usable/remaining capacity and tracked-address counts are exposed
  in list and detail read models and rendered in the UI.
- Released resources and their audit events remain queryable through
  `/subnets/{id}/history` and `/ip-addresses/{id}/history`.
- Department filtering and assignment are available for tracked addresses.

### Validation & safety

- Host-bits-set CIDRs → `422` (creation endpoints reject, calculator normalizes with warning)
- Misaligned subnets → `422`; overlaps/duplicates → `409`; deleting a non-empty network → `409`
- Gateway must sit inside the parent and land on a usable address (allocator pins/grows the block; rejects network/broadcast)
- Errors always `{"error":{code,message,details}}`; no stack traces or internals leaked
- Plan activation commits all subnets or none (tested conflict cases roll back)

## Verification evidence

| Check | Result |
| --- | --- |
| `backend: pytest -q` | **204 passed** (engine, API, auth, inventory, concurrency, migrations, exports) |
| `backend: ruff check .` | **clean** (E, F, I, W) |
| `frontend: npm run build` (tsc + vite) | **clean** |
| `frontend: npm run lint` (oxlint) | **clean** (one pre-existing `ui.tsx` advisory warning) |
| Headless UI smoke | **27 checks passed** against backend `:8001` + Vite `:5174`: login, dashboard, nav, dialogs, toasts, validation error, 375 px mobile layout, lifecycle/history UI |
| Role walkthrough | viewer/operator dashboards render without errors; admin Users page lists accounts; subnet utilization meters and history dialog verified |
| Seeded dataset | 12 networks, 42 subnets, 82 tracked IPs, 3 plans, 153 audit events, 3 role accounts |

## Notes & limitations

- **M8–M10 not yet delivered**: governance reporting, reliability/security/performance certification, and deployment/backup/restore evidence remain open.
- **Docker not executed here**: no Docker daemon is available on this machine. Dockerfiles and `docker-compose.yml` follow standard patterns (python:3.12-slim + node:22-alpine build + nginx proxy) but were not built/run locally. M10 requires replacement evidence from a Docker-capable environment or an approved equivalent.
- **UI verified headless**: functional flows are click-tested with Chromium; GPU compositor behaviour is not covered (risk R-04).
- Default DB is SQLite (`backend/netspace.db`); set `NETSPACE_DATABASE_URL` for
  PostgreSQL and run `alembic upgrade head`. The seed backs up the SQLite file before resetting.
- PDF/XLSX/CSV exports are landscape-A4 oriented; the print stylesheet hides
  navigation/actions and repeats table headers across pages.
