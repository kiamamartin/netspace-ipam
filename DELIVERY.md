# NetSpace IPAM — Delivery Report

Date: 2026-10-15 · Algorithm version: `vlsm-1.0.0`

## What was delivered

| Area | Delivered |
| --- | --- |
| Calculation engine | IPv4/IPv6 subnet math, VLSM allocator, split/summarize, structural checks |
| API | FastAPI `/api/v1`: calculator, networks, subnets, IPs, departments, plans, reports, dashboard, audit |
| Persistence | SQLAlchemy models + Alembic migrations (upgrade/downgrade verified by tests), SQLite default, any SQLAlchemy URL via `NETSPACE_DATABASE_URL` |
| Plans | Draft → activate (transactional) → recalculate → archive lifecycle with conflict detection |
| Frontend | React 19 + TS (Vite): Dashboard, Calculator, VLSM Planner, Plans, Networks, IP Addresses, Departments |
| Reports | CSV (metadata preamble), XLSX (4 sheets), PDF (uncompressed streams, greppable) + print stylesheet |
| Ops | Dockerfiles (backend, frontend/nginx), `docker-compose.yml`, `.env.example`, docs |

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

### Validation & safety

- Host-bits-set CIDRs → `422` (creation endpoints reject, calculator normalizes with warning)
- Misaligned subnets → `422`; overlaps/duplicates → `409`; deleting a non-empty network → `409`
- Gateway must sit inside the parent and land on a usable address (allocator pins/grows the block; rejects network/broadcast)
- Errors always `{"error":{code,message,details}}`; no stack traces or internals leaked
- Plan activation commits all subnets or none (tested conflict cases roll back)

## Verification evidence

| Check | Result |
| --- | --- |
| `backend: pytest -q` | **155 passed** (engine, API, invariants, migrations, exports) |
| `backend: ruff check .` | **clean** (E, F, I, W) |
| `frontend: npm run build` (tsc + vite) | **clean** |
| `frontend: npm run lint` (oxlint) | **0 warnings, 0 errors** |
| End-to-end via dev server | Vite on `:5173` proxies to uvicorn; verified health, dashboard, network create, subnet allocate (201), misaligned subnet (422), VLSM preview, plan save + activate (2 subnets created), IP register, all **6 report exports** (200; CSV preamble + header on row 5; PDF starts `%PDF-`), dashboard metrics update |

## Notes & limitations

- **Docker not executed here**: no Docker daemon on this machine. Dockerfiles and
  `docker-compose.yml` follow standard patterns (python:3.12-slim + node:22-alpine
  build + nginx proxy) but were not built/run locally.
- **UI verified over HTTP, not click-tested**: no browser available in this
  environment; every page's data path was exercised through the dev-server proxy
  (`localhost:5173`) with real backend responses, and the production build type-checks.
- Default DB is SQLite (`backend/netspace.db`); set `NETSPACE_DATABASE_URL` for
  PostgreSQL and run `alembic upgrade head`.
- PDF/XLSX/CSV exports are landscape-A4 oriented; the print stylesheet hides
  navigation/actions and repeats table headers across pages.
