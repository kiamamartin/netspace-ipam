# M6/M7 — Frontend Workflows and IPAM Inventory

> **Authority:** `MILESTONES.md` §6 and §7. This file is the executed evidence
> record for the M6 and M7 gates.

## Environment

- Backend: FastAPI / SQLAlchemy / SQLite, seeded enterprise dataset.
- Frontend: React + TypeScript + Vite.
- This host already runs unrelated services on `:8000` and `:5173`, so the
  verification used backend `:8001` and Vite `:5174` with
  `NETSPACE_BACKEND_URL=http://localhost:8001`.
- Browser automation: headless Chromium (`smoke.mjs` and the repository
  browser harness). No GPU assertions are made (risk R-04).
- Seeded accounts were created with operator-supplied `NETSPACE_SEED_*`
  passwords. Passwords are intentionally absent from this document.

## M6 — Frontend and Operator Workflows

### Scope and deliverables

Responsive forms, calculator, VLSM workspace, tables, validation, loading /
error / empty states, and real API integration.

### Acceptance criteria evidence

| Criterion | Evidence |
| --- | --- |
| M6-AC-001 — Real API integration | Login, dashboard, network/department dialogs, plans, calculator, VLSM planner and reports all ran against the live backend on `:8001`. Login uses `POST /api/v1/auth/login` then resolves identity through `GET /api/v1/auth/me`. |
| M6-AC-002 — Loading, error, validation, empty states | Smoke run exercised page loading, dialog submit toasts, empty-state markup and the network validation error. New history and users pages render explicit loading, empty and error branches. |
| M6-AC-003 — Mobile layouts | Headless run at 375×812: dashboard rendered all four stat cards with 0 px document overflow; the networks table stayed inside `.table-wrap` with 0 px page overflow. |
| M6-AC-004 — No duplicated authoritative calculations | Calculator, split/summarize and VLSM planner call `/api/v1/calculator/*`; plan saving and activation call `/api/v1/allocation-plans/*`. The UI renders backend results rather than recomputing them. |
| M6-AC-005 — Backend validation errors surface | Entering an invalid network CIDR produced a visible backend 422 toast/banner in the smoke run. |
| M6-AC-006 — No placeholder metrics | Dashboard values came from the seeded database (12 networks, 82 tracked IPs, 20.3% utilization, 3 plans in the verified run). |

### Verification results

```
frontend$ npm run lint   -> exit 0
  one pre-existing warning: react(set-state-in-effect) in src/ui.tsx

frontend$ npm run build  -> exit 0
  tsc -b clean
  vite build: 450 modules, dist/assets/index-BdayQkoo.js 594.05 kB

frontend$ SMOKE_BASE=http://localhost:5174 \
  SMOKE_USER=admin SMOKE_PASS=... \
  EDGE_PATH=/usr/bin/chromium-browser node smoke.mjs

  27 PASS checks
  PASS login
  PASS dashboard stats / meters
  PASS sidebar nav (8 links for admin)
  PASS theme toggle / persistence / restore
  PASS calculator split
  PASS planner number inputs
  PASS plan detail
  PASS network dialog / row menu / confirm dialog
  PASS dialog stacking, backdrop, focus trap, modal crispness
  PASS department create/delete round trip
  PASS IP filters
  PASS validation surface (invalid CIDR -> visible backend error)
  PASS mobile dashboard (375 px, 0 px overflow)
  PASS mobile tables (.table-wrap, 0 px page overflow)
  PASS subnet owner/location columns
```

The smoke problem collector also recorded the expected negative 422 response
and an aborted `DELETE` caused by the self-cleaning department fixture; neither
is a UI failure. No unexpected console errors or failed requests were observed
in the role walkthrough.

## M7 — IPAM Inventory and Lifecycle Management

### Scope and deliverables

Searchable inventory with departments, parent networks, child subnets,
ownership/location, utilization, reservations, release, and allocation history.

### Acceptance criteria evidence

| Criterion | Evidence |
| --- | --- |
| M7-AC-001 — Sites, departments, networks, subnets | `test_ac001_create_sites_departments_networks_subnets` creates each resource through the API. Seed creates 14 departments and 12 networks. |
| M7-AC-002 — Status, owner, purpose, location, lifecycle | `test_ac002_owner_purpose_location_lifecycle_tracked` covers create/update of owner, location, description and status. Network detail UI displays owner and location; lifecycle actions are available from each subnet row. |
| M7-AC-003 — Search and filters | `test_ac003_search_and_filters` covers CIDR, department, site, status and ownership filters. UI exposes network text/status/environment filters, subnet text/status filters, and IP address text/status/subnet/department filters. |
| M7-AC-004 — Utilization and remaining capacity | `test_ac004_utilization_and_remaining_capacity` validates total/usable/assigned/reserved/remaining values and the percentage. The subnet list and network detail read models now return `ip_address_count` and `utilization`; the detail table renders a meter, used/usable counts and free capacity. |
| M7-AC-005 — Reservation and release | `test_ac005_subnet_reservation_release_workflow` and `test_ac005_ip_reservation_release_workflow` cover both resource types, including forced subnet release when addresses exist. UI actions call `POST /subnets/{id}/reserve`, `POST /subnets/{id}/release?force=true`, `POST /ip-addresses/{id}/reserve` and `POST /ip-addresses/{id}/release`. |
| M7-AC-006 — History preserved | `test_ac006_history_preserved_when_address_space_changes` verifies released rows and their audit history survive. UI history dialogs read `/api/v1/subnets/{id}/history` and `/api/v1/ip-addresses/{id}/history`; a seeded subnet’s history was rendered in the browser. |
| M7-AC-007 — Conflicting/duplicate reservations rejected | `test_ac007_conflicts_and_duplicate_allocation_rejected` covers duplicate and overlapping requests. |
| M7-AC-008 — Concurrency | `tests/concurrency/` passed: identical subnet allocations, identical IP registrations, and overlapping subnet attempts persist at most one winner. |

### Verification results

```
backend$ pytest tests/test_inventory.py tests/concurrency -q
  11 passed

backend$ pytest tests/test_auth.py -q
  12 passed
  (includes operator/viewer access to /api/v1/dashboard/summary with embedded
   recent_activity, so non-admin dashboards do not call admin-only audit events)

backend$ pytest -q
  204 passed

backend$ ruff check .
  All checks passed!
```

### Browser verification

- Signed in as `viewer`, `operator` and `admin` against the live stack.
- Viewer and operator dashboards rendered all four stat cards with no error
  banner; viewer/operator nav contained 7 links and `/users` showed
  “Administrator access is required”.
- Admin nav contained 8 links (including Users) and `/users` listed the three
  seeded accounts with role and active state.
- Network detail showed the Utilization column with progress meters and the
  subnet row menu exposed Reserve, Release, View history and Delete actions.
- The View history dialog loaded one audit event for the seeded `SEC-CCTV`
  subnet without console errors or failed requests.

## Seeded dataset used for verification

```
departments: 14
networks: 12
subnets: 42 (37 allocated, 4 reserved, 1 released)
ip addresses: 82
plans: 3 (draft, active, archived)
audit events: 153
accounts: admin, operator, viewer
```

## Residual notes

- R-03/R-04 still apply: visual checks are headless with a transparent dialog
  backdrop and no GPU compositor.
- The smoke test’s problem collector reports the deliberately invalid network
  request (422) and the aborted self-cleaning delete; these are expected.
- Credentials are supplied at seed time through environment variables and are
  not recorded in the repository or this evidence file.
