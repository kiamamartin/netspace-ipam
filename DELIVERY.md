# NetSpace IPAM — Delivery Report

Date: 2026-11-01 · Algorithm version: `vlsm-1.0.0`
Rechecked and updated: 2026-11-05

Delivered scope: **M0–M10** (all Phase 1 gates executed and passed).

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
| Reports | CSV (metadata preamble), XLSX (4 sheets), PDF (uncompressed streams, greppable) + print stylesheet; export endpoints enforce authentication (M8-AC-004) |
| Ops | Docker deployment verified live (compose build+up, backend healthy), `scripts/healthcheck.sh`, `scripts/backup-restore-drill.sh`, `.env.example`, docs, headless UI smoke suite |

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

Re-run 2026-11-05 (M8/M9 gate session):

| Check | Result |
| --- | --- |
| `backend: pytest -q` | **223 passed** (engine, API, auth, inventory, concurrency, migrations, exports, +M9 resilience/input-abuse/performance gates) |
| `backend: ruff check .` | **clean** (E, F, I, W) |
| `frontend: npm run build` (tsc + vite) | **clean** |
| `frontend: npm run lint` (oxlint) | **clean** (one pre-existing `ui.tsx` advisory warning) |
| Performance gate (M9) | subnets list 31.6 ms, dashboard 44.8 ms, subnet detail 11.7 ms, CSV export 9.7 ms — all under documented ceilings (`docs/quality/performance-targets.md`) |
| Headless UI smoke | **27 checks passed** against backend `:8001` + Vite `:5174`: login, dashboard, nav, dialogs, toasts, validation error, 375 px mobile layout, lifecycle/history UI |
| Role walkthrough | viewer/operator dashboards render without errors; admin Users page lists accounts; subnet utilization meters and history dialog verified |
| Seeded dataset | 12 networks, 42 subnets, 82 tracked IPs, 3 plans, 153 audit events, 3 role accounts |

## Milestone recheck (2026-11-05)

Re-verified against `MILESTONES.md` acceptance criteria and
`docs/quality/milestone-status.json`. Verdict for the belief "M10 reached":

**M10 had NOT been reached.** At check start the last PASS gate was M7. The
recheck found and closed the gaps to advance M8 and M9:

| Milestone | Verdict at check start | Action taken this session |
| --- | --- | --- |
| M8 — Governance & Reporting | Implemented but **not passed**: report exports were served without any auth dependency — M8-AC-004 failed | Exports now require a valid token (anonymous `401` before resource resolution, no enumeration); regressions pinned; evidence `docs/baseline/m8-governance-reporting.md` → **PASS** |
| M9 — Reliability, Security & Performance | Partial: concurrency/authz/abuse covered; DB failure/recovery, performance targets, findings report missing | Added `test_resilience.py` (4 tests), `test_input_abuse.py` (12), `test_performance.py` (1) and `docs/quality/{performance-targets,security-findings,recovery}.md`; evidence `docs/baseline/m9-reliability-security-performance.md` → **PASS** |
| M10 — Deployment & Operations | **Not started** (`/health` implemented and tested; structured logging existed, but no deployment/backup/restore evidence) | Executed against the live Docker daemon (R-05 resolved — systemd daemon on `/var/run/docker.sock`; the CLI's desktop context socket was stale): images built fresh, `docker compose up -d --build` → backend healthy; `scripts/healthcheck.sh` → 3 PASS; `scripts/backup-restore-drill.sh` → consistent `VACUUM INTO` snapshot hash-verified container↔host and a **demonstrated taken-down restore** (marker row rolled back, counts 12/42/3 restored); diagnostics doc verified command-by-command. Evidence: `docs/baseline/m10-deployment-operations.md`, `docs/quality/service-diagnostics.md` → **PASS** |

Phase 1 (M0–M10) is fully closed. **M11 (v1.0 release gate) was executed on
2026-11-05**: `make release-check` (new Makefile target) → 223 backend tests,
ruff clean, frontend tsc+vite+oxlint clean; accessibility gate failed on first
run and now **passes with 0 axe violations on all 7 pages** (accessible names
on Ark number/clipboard inputs; `--ok` token darkened to 4.5:1; brand pill
solid background), UI smoke 27 PASS after the change; `docs/USER-GUIDE.md` and
`docs/RUNBOOKS.md` written; risk register assessed — no open release blocker.
Evidence: `docs/baseline/m11-release-certification.md` + logs in
`docs/evidence/m11/`. **Tag AC-006 closed the same day** with operator
authorization: release baseline commit `fcc4bfb` tagged
`netspace-v1.0.0-rc1` (annotated, human identity, no attribution per
AGENTS.md) — **M11 is PASS; Phase 1 (M0–M11) complete.** M12+ belong to
Phase 2 (closed-loop automation, requires PostgreSQL-backed evidence per
R-08).

## Notes & limitations

- **M10 delivered 2026-11-05** against the systemd Docker daemon
  (`DOCKER_HOST=unix:///var/run/docker.sock` — the CLI's `desktop-linux`
  context pointed at an absent Docker Desktop socket and was bypassed). The
  gate run used a port override (API `:18000`, web `:18080`) because host
  8000 is held by an unrelated operator container; compose defaults
  (8000/8080) are unchanged.
- **UI verified headless**: functional flows are click-tested with Chromium; GPU compositor behaviour is not covered (risk R-04).
- Default DB is SQLite (`backend/netspace.db`); set `NETSPACE_DATABASE_URL` for
  PostgreSQL and run `alembic upgrade head`. The seed backs up the SQLite file before resetting.
- PDF/XLSX/CSV exports are landscape-A4 oriented; the print stylesheet hides
  navigation/actions and repeats table headers across pages.
