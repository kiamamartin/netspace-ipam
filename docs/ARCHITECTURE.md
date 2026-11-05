# NetSpace IPAM — Architecture

_Last updated: 2026-11-05 (M11 release certification + Neon service wiring:
WCAG 2.x A/AA axe pass on all pages; Lakebase Postgres (Neon) applied as the
PostgreSQL store via `NETSPACE_DATABASE_URL`; Managed Better Auth wired as a
second identity path — `/neon-signin` SPA page with `@neon/auth`, and
`GET /api/v1/auth/neon/me` validating bearer JWTs against
`NEON_AUTH_JWKS_URL`). See [README.md](README.md) for the docs
maintenance policy that keeps this file current._

## Document map

- **Part I — As-built v1.0** (sections below): the current FastAPI + React
  application, its data flow, UI system, and test surface. This is what exists
  in the repository today.
- **Part II — Target architecture v2.0** (`## Part II` at the end of this file):
  the blueprint for turning the IPAM into a closed-loop network operations
  platform with automated provisioning, configuration drift auditing, device
  inventory, and an execution plane. Part II is a design contract, not a claim
  that the features are implemented.

Part I remains authoritative for the current system. Part II describes the
intended target and the migration path; it must not be read as evidence that a
milestone has passed.

## Overview

```
Browser (React 19 + Ark UI)          FastAPI backend
┌──────────────────────────┐        ┌──────────────────────────────┐
│ App shell (sidebar/topbar)│  HTTP  │ app/api      route handlers  │
│ pages/*      thin views   │ ─────► │ app/services domain + VLSM   │
│ ui.tsx      Ark wrappers  │  JSON  │ app/models   SQLAlchemy ORM   │
│ api.ts      typed client  │ ◄───── │ app/schemas  Pydantic DTOs    │
└──────────────────────────┘        │ db + Alembic migrations      │
                                    └──────────────────────────────┘
```

Every allocation, validation and report is computed server-side; the UI is a
thin client over the REST API (`docs/API.md`).

## Backend (`backend/`)

| Path | Responsibility |
| --- | --- |
| `app/main.py` | App factory, CORS, router mounting, `/health` |
| `app/api/` | Route handlers per resource (networks, subnets, ip-addresses, departments, allocation-plans, calculator, reports, dashboard, audit-events) |
| `app/services/` | Domain logic: IP math, the VLSM engine (`vlsm-1.0.0`), plan activation, report builders (CSV/XLSX/PDF) |
| `app/models/` | SQLAlchemy models (networks, subnets, ip_addresses, departments, plans, audit_events) |
| `app/schemas/` | Pydantic request/response contracts |
| `app/db/` | Engine/session wiring (SQLite by default, `backend/netspace.db`) |
| `migrations/` | Alembic migrations (`alembic upgrade head`) |
| `tests/` | pytest suite (155 tests) + `ruff` lint |
| `scripts/seed_enterprise.py` | Seeds the "Aurora Dynamics" enterprise dataset through the service layer (see [DATA.md](DATA.md)) |

Invariants enforced server-side on every write: containment, alignment,
overlap detection, and a full audit trail per mutation.

## Frontend (`frontend/`)

Vite + React 19 + TypeScript. **Ark UI** (`@ark-ui/react`) provides all
interactive behavior headlessly (accessible dialogs, menus, selects…); the
visual layer is a custom design system in `styles.css` keyed on
`[data-scope='…'][data-part='…']` selectors and CSS custom properties.

| File | Responsibility |
| --- | --- |
| `src/main.tsx` | Entry: `initTheme()` before first paint, then render |
| `src/App.tsx` | Shell: sectioned sidebar, topbar (theme toggle + print), routes, `ToastHost`/`ConfirmHost` mounts |
| `src/api.ts` | Typed fetch client; errors normalized to `ApiError { status, code, message, details }` |
| `src/feedback.ts` | Non-component engines: `toaster`/`notify` (toasts), `confirmAction` (promise-based confirm) |
| `src/theme.ts` | Light/dark state: `data-theme` on `<html>`, localStorage (`netspace-theme`), OS fallback, `useTheme()` hook |
| `src/ui.tsx` | Ark-based primitives + icons (see mapping below) |
| `src/kv.tsx` | Key/value grid helper |
| `src/styles.css` | Full design system: tokens, components, Ark part styling, print stylesheet |
| `src/pages/` | Dashboard, Calculator, Planner, Plans, Networks, IpAddresses, Departments, Users (admin only) |

### UI primitive mapping (page code → Ark component)

| Our wrapper | Ark component | Used for |
| --- | --- | --- |
| `Modal` | `Dialog` | All create/edit forms (networks, subnets, IPs, departments) |
| `confirmAction()` | `Dialog role="alertdialog"` | Replaces `window.confirm` for destructive actions |
| `notify.success/error()` | `Toast` + `createToaster` | Mutation feedback (bottom-end, max 3) |
| `TextField` | `Field` | Labeled inputs with aria wiring + invalid state |
| `SelectField` | `Select` + `createListCollection` | Filters and pickers (environment, status, subnet) |
| `NumberField` | `NumberInput` | Numeric inputs (hosts, VLAN, reserved) |
| `PaginationBar` | `Pagination` | Backend-paginated lists (page window with ellipses) |
| `Meter` | `Progress` | Utilization bars (gradient; `hot` for ≥85%) |
| `RowMenu` | `Menu` | Per-row actions (mark status, reserve/release, history, edit, delete) |
| `HistoryModal` | `Dialog` | Read-only audit/lifecycle history for a subnet or address |
| `Tip` | `Tooltip` | Hover hints on icon buttons |
| `CopyValue` | `Clipboard` | One-click copy of CIDRs/addresses |
| — | `Tabs` | Calculator tool switcher |

### Data flow

- Pages call `api.get/post/patch/delete` → FastAPI; non-2xx becomes `ApiError`
  and is surfaced via `ErrorBanner` + an error toast.
- Mutations end with `notify.*` and a reload of the affected list.
- Destructive actions go through `await confirmAction({...})` first.
- Loading states use `<Loading/>` spinners; submits set `disabled` + busy text.

### Theming (light/dark)

- Single token palette in `:root`; dark overrides in `html[data-theme='dark']`
  (backgrounds, ink, status colors with AA-ish contrast, shadows).
- `initTheme()` (main.tsx) resolves: localStorage → OS `prefers-color-scheme`;
  the toggle in the topbar persists the choice via `setTheme()`.
- Component colors must use tokens (`--surface`, `--ink`, `--track`,
  `--field-bg`, `--row-hover`, `--danger-line`…) — no raw hex in component
  rules, or dark mode breaks.
- `@media print` re-overrides dark tokens back to light so reports always
  print black-on-white (A4 landscape).
- **Modal blur & focus:** while a dialog is open the background is blurred via
  `body:has([data-scope='dialog'][data-part='backdrop']) .app-shell { filter:
  blur(3px) }` and Ark's modal behavior traps focus inside the dialog (the
  rest of the page becomes inert). The smoke test asserts both (blur computed
  style + 12 Tabs staying inside the content).
- **Caution — GPU compositing:** never put `backdrop-filter` on the dialog
  backdrop or topbar. On GPU-accelerated browsers it can paint above later
  siblings despite `z-index`, hiding the modal behind the blur (fixed
  2026-10-16; headless tests use software rendering and cannot catch this).
  Blur the `.app-shell` (below the portal) instead.

## Testing

| Layer | Command | Notes |
| --- | --- | --- |
| Backend | `cd backend && pytest -q && ruff check .` | 155 tests |
| Frontend build | `cd frontend && npm run build` | `tsc -b` + vite |
| Frontend lint | `cd frontend && npm run lint` | oxlint, 0 warnings expected |
| UI smoke | `cd frontend && npm run test:ui` | Headless Edge (puppeteer-core) against live dev stack; 16 checks: every page, theme toggle + persistence, dialog stacking (`elementFromPoint` guard), CRUD round trip via Dialog/Toast/Menu/AlertDialog |

The smoke test needs backend (`:8000`) and `npm run dev` (`:5173`) running;
screenshots land in the OS temp dir (`netspace-smoke/`). One benign
`requestfailed` for `DELETE /departments/:id` may appear: the delete succeeds
(row disappears, re-list confirms) — it is a dev-proxy connection artifact.

## Known constraints

- Vite warns the single JS chunk exceeds 500 kB (React + Ark's broad module
  graph). Candidate follow-up: route-level code splitting. The `@neon/auth`
  SDK raised the bundle to ~758 kB; the same follow-up applies.
- SQLite by default; the backend is storage-agnostic via SQLAlchemy.
- **Neon (M12 groundwork, 2026-11-05):** project `sparkling-haze-43162404`
  (org `org-floral-sky-07815387`), branch `production`, declared in `neon.ts`
  as `auth: true` and deployed with `neon deploy`.
  - **Store:** pooled `DATABASE_URL` → `NETSPACE_DATABASE_URL` (backend
    `.env`); direct `DATABASE_URL_UNPOOLED` is used only for Alembic/DDL.
    Driver is `psycopg` v3 (`psycopg[binary]`) — SQLAlchemy maps
    `postgresql://` to it. Migrations `0001→0003` verified on Postgres;
    `SELECT … FOR UPDATE` blocking verified (SQLSTATE 55P03).
  - **Auth:** Managed Better Auth in the `neon_auth` schema.
    `NEON_AUTH_BASE_URL`/`NEON_AUTH_JWKS_URL` are injected by Neon;
    `VITE_NEON_AUTH_URL` (frontend `.env.local`) is the browser alias env pull
    does not create. Better Auth stamps `aud`/`iss` with the auth **origin**
    (no `/db/auth` path), so the verifier enforces signature + expiry and
    validates `iss` against that origin; audience is not enforced.
  - v1 username/password bearer auth is unchanged; the Neon identity path is
    additive (`/neon-signin`, `/api/v1/auth/neon/me`).
  - **Entry flow:** after a managed sign-in, the SPA exchanges the Neon JWT at
    `POST /api/v1/auth/neon/session`; the backend provisions a local user keyed
    by email (default role `NETSPACE_NEON_DEFAULT_ROLE`=`viewer`, admin only for
    `NETSPACE_NEON_ADMIN_EMAILS`) and returns the standard app bearer session,
    so the shell opens without a second credential. Disabled local accounts
    stay disabled.

---

## Part II — Target Architecture v2.0: Closed-Loop Network Operations

> **Status:** design blueprint. No Part II capability is implemented until its
> milestone in `MILESTONES.md` is certified with evidence. Test paths and
> commands named in Part II are target contracts, not passing checks.

### 1 Purpose and scope

The current application is a strong **planning and registry** system: it owns
IPv4/IPv6 math, VLSM allocation, subnet containment and overlap invariants, a
transactional plan-activation path, audit events, RBAC, and CSV/XLSX/PDF
reports. It is not yet an **active source of truth**: nothing proves that a
device's running configuration matches the intent recorded in the IPAM.

The v2 target adds two closed loops without replacing the v1 application:

1. **Automated provisioning** — an authorised request (after any required
   approval) reserves IPAM resources, renders a vendor configuration from a
   versioned template, pushes it to a device, verifies the result, and records
   every state transition.
2. **Configuration drift auditing** — a periodic, read-only process compares
   the device's observed configuration with the IPAM-derived desired state,
   stores a redacted diff, scores compliance, and raises deduplicated alerts.

The guiding model is:

| Authority | Owns | Never owns |
| --- | --- | --- |
| **IPAM database** | Intent: sites, VLANs, subnets, IPs, device/interface assignments, desired lifecycle state | Vendor CLI syntax or live device state |
| **Git configuration repository** | Templates, normalisation profiles, approval/drift policy, fixtures, template releases | Inventory records or live device state |
| **Device** | Observed state: running configuration, interface/VLAN reality | Source-of-truth allocation decisions |

#### In scope

- Site, VLAN, device, interface, and IP-to-interface inventory.
- A durable, idempotent job/event backbone.
- A provisioning execution plane with pre-flight checks, dry runs, candidate
  configuration where available, post-checks, and explicit failure semantics.
- A drift audit execution plane with normalisation, redacted diffs, findings,
  compliance scoring, and alert delivery.
- Machine identities, scoped API tokens, secrets-manager integration, and
  tamper-evident operational audit.
- An operations UI for devices, jobs, drift, compliance, schedules, and
  automation settings.

#### Out of scope (for v2.0)

- A full network management system, telemetry collector, or flow analyser.
- Replacing Git with a configuration database; Git remains the template and
  policy authority.
- Autonomous remediation by default. Remediation is opt-in, approval-gated, and
  reuses the provisioning path.
- Multi-tenant isolation. v2 remains single-tenant with site/role scoping.
- Real-time streaming configuration or streaming telemetry.
- IPv6 device provisioning in the first release. IPv6 inventory, calculation,
  and auditing of existing IPv6 sections remain supported; vendor templates
  may add IPv6 later.
- Arbitrary vendor coverage. The first adapters target **Cisco IOS/IOS-XE** and
  **Arista EOS**; the adapter interface is the extension point.

### 2 Current baseline and the delta

| Area | v1.0 today | v2.0 target |
| --- | --- | --- |
| Runtime | FastAPI monolith + React SPA | Same monolith as **control plane**, plus an isolated **execution plane** (relay, workers, scheduler) |
| Database | SQLite by default; SQLAlchemy URL configurable | PostgreSQL in production for row locks, `SKIP LOCKED`, partial indexes, and concurrency; SQLite remains a dev/unit-test convenience |
| Inventory | Networks, subnets, IPs, departments, string `site`, integer `vlan_id` | Adds sites, a site-scoped VLAN registry, devices, interfaces, and IP-to-interface assignments |
| Async work | None; requests are synchronous | Transactional outbox + broker + idempotent workers; API returns `202 Accepted` |
| Auth | Human users with viewer/operator/admin JWT roles | Same human roles plus hashed, scoped machine tokens for auditor/provisioner/worker identities |
| Audit | Append-only `audit_events` per mutation | Adds correlation IDs, job links, source, sanitised before/after data, and operational event history |
| Config | None | Git repository of Jinja2 templates, normaliser profiles, policies, fixtures, and pinned releases |
| Device access | None | Adapter layer over Nornir/Netmiko/Scrapli (SSH) with room for NETCONF/RESTCONF; always over the OOB management network |
| Compliance | Dashboard utilisation/conflicts only | Per-device audit results, drift findings, coverage-aware compliance score, alerting |
| UI | Dashboard, calculator, planner, plans, networks, IPs, departments | Adds sites, VLANs, devices, jobs, drift/compliance, schedules, tokens/webhooks |

The v1 calculation, inventory, plan, report, and auth contracts stay intact.
All schema changes are additive; the legacy `site` and `vlan_id` fields remain
readable and writable until an approved deprecation release.

### 3 Architecture principles and decisions

| # | Principle | Decision and rationale |
| --- | --- | --- |
| D1 | **Modular monolith first** | Keep one FastAPI deployable for the control plane. The application is too small for microservice overhead; bounded modules (`inventory`, `automation`, `compliance`, `identity`, `notification`) keep seams clean. Only the execution plane is a separate deployment. |
| D2 | **Three authorities** | IPAM owns intent, Git owns templates/policy, devices own observed state. No component is allowed to silently become a second source of truth. |
| D3 | **Workers are API clients, not database clients** | Provisioning and audit workers read desired state and report results through the IPAM API with scoped tokens. They never receive database credentials. This preserves the API security boundary and allows independent scaling. |
| D4 | **Durable by construction** | Domain mutation + outbox row commit in one transaction. A relay publishes to the broker. Delivery is at-least-once and every consumer is idempotent. A lost broker message is recoverable from the outbox. |
| D5 | **PostgreSQL for production automation** | Row-level locking, `SELECT ... FOR UPDATE`, `SKIP LOCKED`, partial unique indexes, and real concurrency testing require PostgreSQL. SQLite is supported for local development and pure unit tests, not for multi-worker automation. |
| D6 | **Celery + Redis for execution** | Celery provides routing, retries, and operational familiarity; Redis is the broker. Celery results are not authoritative: `automation_jobs` is. A `TaskPublisher` boundary allows a lighter queue to replace Celery later. |
| D7 | **One mutating job per device** | An exclusive `device_locks` lease serialises configuration pushes. Audits do not overlap a push. This prevents two operators or two retries from racing the same device. |
| D8 | **Safe push, not optimistic push** | Every push has pre-flight validation, a dry-run capability, a rendered-config hash, and a post-check. Candidate-config/commit is preferred. Blind rollback on legacy platforms is forbidden; failure produces an explicit compensation/reconciliation state. |
| D9 | **Drift is advisory; remediation is opt-in** | Auditing never writes to a device. Remediation is a separate job type requiring policy and, for production, approval. |
| D10 | **Pin template releases** | A device resolves templates at a pinned Git release/commit, not at `main`. A Git commit therefore cannot silently redefine desired state and generate false drift. Promotion is an explicit operation. |
| D11 | **Secrets never land in the IPAM** | Devices store a `credential_ref` (Vault/secret-manager path), never a password or key. Workers resolve credentials at runtime. Logs, job payloads, snapshots, and diffs are redacted. |
| D12 | **Coverage-aware compliance** | A compliance score is always shown with audit coverage. Unreachable/errored devices are not silently excluded to manufacture 100%. |
| D13 | **Additive, reversible migration** | New nullable columns/tables, backfills with dry-run reports, dual-write for legacy site/VLAN fields, feature flags for execution-plane rollout. No destructive migration without a separate approved change. |
| D14 | **Observable by default** | Every job, audit, event, and device interaction carries a correlation ID. Queue lag, lease expiry, drift counts, and device reachability are metrics, not log-only facts. |

**Dependency note:** the blueprint introduces new runtime dependencies (Celery,
a Redis client, a PostgreSQL driver, croniter, Jinja2, Nornir, Netmiko/Scrapli,
and a secrets-manager client).
Per repository policy, each is an approval-gated milestone decision. They are
isolated behind `TaskPublisher`, `Renderer`, `DeviceAdapter`, and `SecretsProvider`
interfaces so an alternative can be substituted without changing the
control-plane contracts.

**Alternatives considered and rejected for v2.0**

- **Full microservices split** — rejected: the control-plane domain is tightly
  coupled (allocation invariants span networks/subnets/IPs) and the team-scale
  benefit does not justify distributed transactions or extra operations.
- **Direct worker database access** — rejected: it collapses the API security
  boundary, complicates secret isolation, and makes the worker a second writer
  of inventory state.
- **Celery result backend as job state** — rejected: broker state is not
  durable business state and is not queryable by the UI/audit.
- **Auto-remediation on every drift** — rejected for v2.0: normalisation false
  positives and out-of-band operational changes can make automated pushes
  dangerous. Remediation remains approval-gated.
- **Compare raw configurations directly** — rejected: dynamic lines and vendor
  formatting produce false positives. Normalisation and fingerprints are
  mandatory.

### 4 System context and trust boundaries

```
                    ┌─────────────────────────────────────────┐
                    │ Operators · ITSM/Service Portal · CI    │
                    └───────────────┬─────────────────────────┘
                                    │ HTTPS · JWT · signed webhooks
                                    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ CONTROL PLANE                                                             │
│                                                                           │
│  ┌──────────────────────┐        ┌────────────────────────────────────┐   │
│  │ React UI             │───────▶│ FastAPI IPAM API                   │   │
│  │ (thin client)        │  JSON  │ inventory · allocation · plans     │   │
│  └──────────────────────┘        │ automation · compliance · auth     │   │
│                                  │ desired-state · webhooks           │   │
│                                  └───────┬─────────────────┬──────────┘   │
│                                          │                 │              │
│                                  ┌───────▼───────┐   ┌─────▼──────────┐   │
│                                  │ PostgreSQL    │   │ Outbox relay   │   │
│                                  │ intent + jobs │   │ (control plane)│   │
│                                  │ + audit       │   └─────┬──────────┘   │
│                                  └───────────────┘         │              │
│                                                            │ publish      │
│                                  ┌─────────────────────────▼──────────┐   │
│                                  │ Redis / Celery broker              │   │
│                                  └─────────────────────────┬──────────┘   │
└────────────────────────────────────────────────────────────┼──────────────┘
                                                             │
┌────────────────────────────────────────────────────────────▼──────────────┐
│ EXECUTION PLANE — no database credentials                                 │
│                                                                           │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌──────────────────┐  │
│  │ Provisioning worker │  │ Drift audit worker  │  │ Scheduler        │  │
│  │ render · push ·     │  │ collect · normalise │  │ audit schedules  │  │
│  │ verify              │  │ · diff · report     │  │ · manual runs    │  │
│  └───────┬─────────────┘  └───────┬─────────────┘  └────────┬─────────┘  │
│          │                        │                         │            │
│  ┌───────▼─────────────┐  ┌───────▼─────────────┐  ┌───────▼─────────┐  │
│  │ Device adapters     │  │ Git template repo   │  │ Secrets manager  │  │
│  │ Nornir · Netmiko ·  │  │ pinned release      │  │ Vault / KMS      │  │
│  │ Scrapli / RESTCONF  │  │ read-only deploy key│  │ short-lived cred │  │
│  └───────┬─────────────┘  └─────────────────────┘  └──────────────────┘  │
└──────────┼────────────────────────────────────────────────────────────────┘
           │ SSH / NETCONF / RESTCONF over the OOB management network
           ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ PRODUCTION NETWORK FABRIC — switches · routers · firewalls               │
└───────────────────────────────────────────────────────────────────────────┘
```

**Trust boundaries and forbidden paths**

| From → To | Allowed | Control |
| --- | --- | --- |
| UI/ITSM → API | HTTPS | JWT or scoped bearer token, CORS allowlist, rate/body limits |
| API → PostgreSQL | Private network | TLS, least-privilege DB role, migrations by a separate role |
| API/relay → Redis | Private network | TLS/auth where supported; broker is not exposed to users |
| Worker → API | HTTPS | Scoped machine token; optional mTLS; internal routes restricted by network policy |
| Worker → Vault | HTTPS | Short-lived token scoped to one device credential path; no fallback to cached secrets |
| Worker → Git | HTTPS/SSH | Read-only deploy key; pinned commit verification |
| Worker → device | SSH/NETCONF/RESTCONF | OOB management network, host-key verification, per-device credentials |
| API → device | **Forbidden** | The control plane never opens a device session |
| Worker → PostgreSQL | **Forbidden** | Workers have no DB credentials by design |
| Device → API | **Forbidden** | Devices are not agents; no inbound path |

### 5 Logical components

| Component | Responsibility | Scaling unit |
| --- | --- | --- |
| **React UI** | Thin operator client: inventory, devices, jobs, drift, compliance, settings | Static assets/CDN or nginx |
| **IPAM API** | Authn/authz, inventory/allocation, plan lifecycle, automation job API, desired-state assembly, compliance read models, webhook admin, outbox writes | Stateless replica |
| **Outbox relay** | Claim unpublished outbox rows, publish to Celery/Redis, mark published, retry with backoff | 1–N replicas (`FOR UPDATE SKIP LOCKED`) |
| **Scheduler** | Read `audit_schedules`, create one audit run per due slot, enqueue per-device audit jobs via the API | Single active replica; DB unique slot prevents duplicates |
| **Provisioning worker** | Claim job, render config, resolve secrets, pre-flight, push, post-check, report | N workers; one mutating job per device |
| **Audit worker** | Claim audit job, fetch desired state, collect running config, normalise, diff, submit result/findings | N workers; read-only device access |
| **Notification dispatcher** | Deliver signed webhook events to Slack/Teams/PagerDuty/ITSM, retry, record deliveries | 1–N replicas |
| **Renderer** | Jinja2 sandboxed rendering with strict undefined, template release pin, output hash, no-op detection | Library inside execution plane |
| **Normaliser** | Per-platform redaction/canonicalisation rules, stable fingerprints, unified diff | Library inside execution plane |
| **Device adapters** | Uniform connect/pre-flight/read/load/commit/rollback/verify interface over vendor drivers | Library inside execution plane |
| **Git repository** | Templates, normalisers, policies, fixtures, release manifest | External, versioned |
| **Secrets manager** | Device credentials and webhook secrets resolved at runtime | External |
| **PostgreSQL** | Intent, job state, outbox, audit runs/results/findings, tokens, webhook deliveries | Managed HA in production |
| **Redis** | Celery broker; no business state | Managed/HA in production |
| **Object storage (optional)** | Raw encrypted config snapshots above a size threshold | External |
| **Observability stack** | Structured logs, metrics, traces, alerting | Platform-provided |

**Bounded modules in the API**

- `inventory` — sites, networks, subnets, VLANs, IPs, departments.
- `allocation` — VLSM, next-available IP/VLAN allocation, plan activation.
- `automation` — devices, interfaces, jobs, schedules, tokens, webhooks,
  desired-state assembly, internal worker callbacks.
- `compliance` — audit runs, results, findings, score read models.
- `identity` — users, roles, machine tokens, permission checks.
- `notification` — outbox event fan-out and webhook delivery.

Route handlers stay thin; invariants live in services. The v1 service layer is
retained and extended, not bypassed.

**Notification dispatcher boundary:** the dispatcher is a control-plane
component with database access to `webhook_endpoints` and
`webhook_deliveries`. It consumes notification events from the broker, resolves
secrets from Vault, signs and delivers payloads, and records delivery attempts.
It never touches devices or inventory writes. This is a deliberate exception to
the worker rule, which applies to the device-facing execution plane.

### 6 Deployment topology

**Development (Docker Compose profiles)**

| Profile | Services |
| --- | --- |
| `core` | `web`, `api`, `postgres` |
| `automation` | `redis`, `outbox-relay`, `notification-dispatcher`, `worker-provisioning`, `worker-audit`, `scheduler` |
| `observability` | Optional Prometheus/Grafana/OTel collector |

SQLite remains available for calculator/unit tests and a zero-dependency
single-user demo. Any test/feature that depends on row locks, `SKIP LOCKED`, or
concurrent workers must run against PostgreSQL.

**Production**

- Ingress terminates TLS 1.3; only the UI and public API are exposed.
- API replicas behind the ingress; outbox relay and notification dispatcher are
  separate deployments.
- Execution-plane processes run as Linux containers; the Windows development
  setup used for the v1 control plane is not a supported worker host.
- Workers run in the management zone with egress only to the OOB device network,
  Git, Vault, Redis, the API, and (if enabled) encrypted object storage. They do
  not run on the public user network.
- PostgreSQL has PITR and a read replica where required; Redis is private.
- Scheduler has one active instance; its audit-run uniqueness is enforced by the
  database, so a brief duplicate scheduler does not duplicate audits.
- Network policies block public access to `/api/v1/internal/*`, PostgreSQL,
  Redis, Vault, and Git.
- Worker concurrency is conservative per site: provisioning concurrency is
  limited by device locks, audit concurrency by device reachability and site
  rate limits. Site-level limits prevent a full-fleet audit from saturating the
  OOB network.

**Backup and recovery:** PostgreSQL PITR, Git remote backups, Vault backups,
optional object-store lifecycle rules. A restore drill must prove that job
state, outbox rows, audit results, and findings survive recovery; broker state
is reconstructible from the outbox and is not treated as a backup source.

### 7 Domain model and schema extensions

#### 7.1 Entity map

```
sites 1──* networks 1──* subnets 1──* ip_addresses
  │            │             │              ▲
  │            │             └─? vlan_ref   │
  │            └─* (site_id)                 │
  │                                          │
  └──* devices 1──* device_interfaces 1──* interface_ip_assignments
            │                  │
            │                  ├──* interface_allowed_vlans *──1 vlans
            │                  └──? access_vlan_ref_id / native_vlan_ref_id
            │
            └──* automation_jobs 1──* automation_job_steps
                           │
                           ├──? config_snapshots
                           └──? device_locks

audit_schedules 1──* audit_runs 1──* audit_results 1──* drift_findings
                                           │
                                           └──? config_snapshots
```

Legacy relationships (`networks.site` text, `subnets.vlan_id` integer,
`ip_addresses.device` text) remain during migration. The new relationships are
the target authority; services dual-read/dual-write where compatibility
requires it.

#### 7.2 New and changed entities

| Entity | Purpose | Key constraints |
| --- | --- | --- |
| `sites` | Stable site registry for scoping devices, VLANs, and allocation policy | `code` unique; `name` unique |
| `vlans` | Site-scoped VLAN registry and lifecycle state | `(site_id, vlan_id)` unique; `vlan_id` 1–4094 |
| `devices` | Managed network device inventory | `hostname` canonical/unique; `management_ip` unique; `credential_ref` only (required when `config_managed` or `audit_enabled`) |
| `device_interfaces` | L2/L3 interface inventory and observed state | `(device_id, name)` unique |
| `interface_allowed_vlans` | Trunk allowed-VLAN membership with referential integrity | `(interface_id, vlan_ref_id)` unique |
| `interface_ip_assignments` | IPAM address ↔ device interface assignment | `(interface_id, ip_address_id)` unique |
| `automation_jobs` | Durable provisioning/audit/remediation job state, including parent/child grouping for cross-device intent | `idempotency_key` unique; UUID id; explicit state machine; parent is never claimed |
| `automation_job_steps` | Safe, redacted job timeline | `(job_id, seq)` unique |
| `outbox_events` | Transactional event publication | `event_id` unique; retry metadata |
| `idempotency_records` | API request replay protection | key + request hash; TTL |
| `device_locks` | Exclusive per-device mutation lease | one row per device; expiry/heartbeat |
| `config_snapshots` | Golden/live snapshots, hashes, template release | content redacted; hash indexed |
| `audit_schedules` | Recurring audit definitions | cron/scope/enabled; `next_run_at` |
| `audit_runs` | One logical audit sweep | unique `(schedule_id, scheduled_for)` |
| `audit_results` | Per-device outcome within a run | `(audit_run_id, device_id)` unique |
| `drift_findings` | Stable finding lifecycle across runs; config drift vs deployment gap | partial unique `(device_id, fingerprint)` while unresolved |
| `change_records` | Per-device change evidence for remediation/provisioning | job/device/actor/approval/outcome; retained as compliance record |
| `change_record_findings` | Change record ↔ drift finding linkage | `(change_record_id, finding_id)` unique |
| `api_tokens` | Hashed machine credentials | `token_hash` unique; scopes/expiry |
| `webhook_endpoints` | Outbound notification/ITSM targets | `secret_ref` only; event-type filter |
| `webhook_deliveries` | Delivery audit and retry state | `(endpoint_id, event_id)` unique |

**Changed existing tables**

| Table | Additions | Compatibility |
| --- | --- | --- |
| `networks` | `site_id` nullable FK | `site` text retained |
| `departments` | `site_id` nullable FK | `site` text retained |
| `subnets` | `vlan_ref_id` nullable FK, `provisioning_status`, `last_job_id`, `desired_config_hash`, `observed_config_hash`, `last_audited_at` | `vlan_id` retained and dual-written |
| `ip_addresses` | `provisioning_status`, `last_job_id` | `device` text retained for compatibility; device/interface linkage lives only in `interface_ip_assignments` |
| `audit_events` | `correlation_id`, `job_id`, `source`, `details` (sanitised JSON) | Existing columns unchanged |

`provisioning_status` is deliberately **orthogonal** to the existing lifecycle
`status` fields. `status` answers the existing resource lifecycle question
(allocated/planned/reserved/released for subnets;
assigned/available/reserved/deprecated for IPs); `provisioning_status` answers
"has this intent reached the device?" Values:

`not_requested · pending_deploy · deploying · active · failed · deprovisioning · deprovisioned`

Existing rows default to `not_requested`; a successful baseline audit or an
approved provisioning job moves them to `active`. The proposal's original
`DEFAULT 'active'` is rejected because it would claim deployment success that
never occurred.

`devices.compliance_status` is `unknown · compliant · drifted · error ·
disabled`. `devices.criticality` is `low · medium · high · critical` and is used
for weighted rollups, not for silently changing the raw counts.

Devices referenced by jobs, findings, or snapshots are **retired, not hard
deleted**: clear `config_managed`/`audit_enabled`, set
`status = 'decommissioned'` and `compliance_status = 'disabled'`. Deletion is
allowed only for never-referenced inventory rows, so audit history cannot
disappear through a cascade.

#### 7.3 State machines

**Automation job**

```
                 approve                claim                 success
pending_approval ───────▶ queued ───────────────▶ running ─────────────▶ succeeded
      │                     │                       │
      │ reject/cancel       │ cancel                ├── retryable failure ──▶ queued (attempt+1)
      ▼                     ▼                       │
  cancelled             cancelled                   ├── final failure ──────▶ failed
                                                    ├── mixed child results ─▶ partial
                                                    └── lease expiry ────────▶ queued

queued/running ── cancel requested ──▶ cancel_requested ── worker ack ──▶ cancelled
```

Rules:

- `pending_approval` is used only when policy requires approval for the target
  environment/site/device criticality.
- `partial` is terminal and applies to parent jobs whose children ended in a
  mix of success and failure. Retrying failed children creates new child jobs;
  the parent is not silently reopened.
- A job can be claimed only from `queued`; the claim is atomic and sets a
  lease (`lease_owner`, `lease_expires_at`, `heartbeat_at`).
- Parent jobs are advanced by child-state aggregation in the API, never by a
  worker claim; only children hold leases and device locks.
- An expired lease is recoverable: the reaper requeues the job and increments
  the attempt. If the device already received the configuration, the next
  attempt must detect it via the rendered-config hash and become a verified
  no-op rather than a duplicate push.
- `cancel_requested` is not a guarantee after a configuration commit. If the
  change was committed, cancellation becomes a compensation/remediation job;
  the platform never pretends a committed change was rolled back.

**Resource deployment state**

```
not_requested ── job queued ──▶ pending_deploy ── worker start ──▶ deploying
      ▲                               │                              │
      │                               └── cancel before push ────────┤
      │                                                              ├── post-check OK ──▶ active
      │                                                              └── failure ─────────▶ failed
      └── release ──▶ deprovisioning ──▶ deprovisioned        active/failed ──▶ deprovisioning
```

Drift is **device-level**, not a resource provisioning state. A resource stays
`active` while its device carries an open drift finding. This avoids corrupting
allocation lifecycle with transient configuration observations.

For a resource that spans devices, `provisioning_status` becomes `active` only
when every target child job succeeded. A `partial` parent leaves the resource
`pending_deploy` or `failed`, and the next audit reports a `deployment_gap`
rather than claiming success.

**Drift finding**

```
open ── acknowledge ──▶ acknowledged ── resolve (absent on later successful audit) ──▶ resolved
  │                                                                     ▲
  ├── accept risk ──▶ accepted ── expiry/review ────────────────────────┘
  └── absent on later successful audit ─────────────────────────────────┘
```

A finding is resolved only by a successful audit that no longer reproduces its
fingerprint, not merely because a newer audit started. An unreachable device
does not resolve findings.

**Device compliance**

`unknown → compliant | drifted | error`, with `disabled` for unmanaged devices.
`error` covers authentication failure, timeout, and adapter errors; it is never
counted as compliance.

#### 7.4 Data classification and retention

| Data | Classification | Storage and retention |
| --- | --- | --- |
| Inventory intent (sites, subnets, IPs, assignments) | Internal | PostgreSQL; retained for the life of the record + audit history |
| Job payload/results | Internal | PostgreSQL; default 90 days, configurable |
| Job steps | Internal | PostgreSQL; default 30 days, redacted |
| Transactional outbox | Internal | Published rows 30 days; unpublished/dead-letter rows retained until resolved |
| Idempotency records | Internal | 24 hours after the original response (configurable) |
| Webhook deliveries | Internal | 30 days; dead-letter rows retained until acknowledged |
| Device locks | Internal | Deleted on release or lease expiry |
| Redacted golden/live snapshots and diffs | Internal, potentially sensitive | PostgreSQL; default 90 days; restricted read scope |
| Raw device config | Confidential | Object storage encrypted at rest, default 7 days; never in logs; optional |
| Credentials, keys, webhook secrets | Secret | Secrets manager only; **never** in PostgreSQL, Git, job payloads, logs, or snapshots |
| Audit events | Compliance record | Append-only; default 1 year; tamper-evidence option in M17 |
| Compliance results/findings | Compliance record | Results 1 year; open findings retained until resolved + 90 days |
| Change records and their finding links | Compliance record | Default 1 year; retained with job/device/approval evidence |
| API tokens | Secret | Store only a hash and prefix; revoke/rotate; never recoverable |

Retention deletion is order-aware. An `audit_results` row referenced by an
unresolved finding, or by a snapshot still within its retention window, is
archived or skipped, never cascade-deleted. Purging a run must not erase open
findings or their evidence. A job referenced by a `change_records` row is kept
until that change record expires; change records are deleted before their
referenced jobs.

Redaction happens **before** persistence and before diff storage. Secret-bearing
lines are replaced with a stable marker. Where policy needs to detect a changed
secret without exposing it, compare a keyed hash of the secret line rather than
the clear value.

### 8 Workflow A — Automated provisioning

#### 8.1 End-to-end sequence

```
Client/ITSM        API                    PostgreSQL        Relay        Worker        Device
    │               │                        │               │             │             │
    ├─ POST job ───▶│                        │               │             │             │
    │  Idempotency  ├─ BEGIN ───────────────▶│               │             │             │
    │  -Key         │  validate + authorize  │               │             │             │
    │               │  lock intent rows      │               │             │             │
    │               │  create job + steps    │               │             │             │
    │               │  outbox row            │               │             │             │
    │               ├─ COMMIT ──────────────▶│               │             │             │
    │◀─ 202 job ────┤                        │               │             │             │
    │               │                        ├─ claim ──────▶│             │             │
    │               │                        │               ├─ publish ──▶│             │
    │               │◀─ claim/heartbeat ─────┼───────────────┼─────────────┤             │
    │               │                        │               │             ├─ desired ──▶│
    │               │                        │               │             │  state API  │
    │               │                        │               │             ├─ preflight ▶│
    │               │                        │               │             ├─ render     │
    │               │                        │               │             ├─ push ──────▶│
    │               │                        │               │             ├─ post-check ▶│
    │               │◀─ complete(result) ────┼───────────────┼─────────────┤             │
    │               ├─ update job/resources  │               │             │             │
    │               ├─ audit + outbox ──────▶│               │             │             │
    │◀─ events ─────┼────────────────────────┴───────────────┴─────────────┘             │
```

#### 8.2 API boundary and request lifecycle

1. The client calls `POST /api/v1/automation/jobs` with an `Idempotency-Key`.
   Human callers use a JWT; ITSM uses a scoped machine token.
2. The API validates the payload against the job-type schema and checks the
   caller's scope, site/device scope, and approval policy.
3. In one database transaction the API:
   - locks the allocation sources in a fixed order (`site` → `vlan` → `subnet`
     → `ip` → `device`), using `SELECT ... FOR UPDATE` in PostgreSQL;
   - allocates the requested resources or verifies explicit ones;
   - writes `automation_jobs` and `automation_job_steps`;
   - writes the `idempotency_records` row (key, request hash, response
     status/body);
   - for a job that does not require approval, sets
     `provisioning_status = pending_deploy` on affected resources (skipped for
     `dry_run=true`; the proposed allocation is recorded in the job result);
   - for a job that requires approval, stores only the validated request and
     does not allocate or transition resources;
   - writes `outbox_events`: `automation.job.approval_requested` to the
     notification destination when approval is required, or
     `automation.job.requested` to the job destination when immediately
     queueable;
   - writes an `audit_events` row with the actor, correlation ID, and job ID.
4. Commit. Return `202 Accepted` with the job ID, status, and links. No device
   I/O happens in the request.

If approval is required, the request stops at `pending_approval`. The approve
transaction revalidates the intent, allocates and transitions the resources,
writes the outbox event, and moves the job to `queued`; a rejected or expired
approval leaves resources untouched because nothing was reserved before
approval.
5. The relay claims the outbox row and publishes it to every queue named by
   `destination` (`jobs`, `notifications`, or `both`); job events carry `job_id`
   and are routed to the queue for their job type. Duplicate publishes are
   harmless; a partial publish is retried and consumers dedupe by `event_id`.
6. A worker claims the job through the internal API. The claim transaction
   checks status, lease, and the device lock. A second worker gets
   `409 device_busy` or `409 job_not_claimable` and does not touch the device.
7. The worker fetches the device's desired-state document, resolves credentials,
   renders, pre-flights, pushes, post-checks, and submits a completion report.
   For `dry_run=true` it stops after read-only collection, rendering, and diff
   generation; it never loads a candidate or commits.
8. The API applies the completion transaction: job state, resource state,
   snapshots, audit events, outbox events. If the job failed, the failure is
   recorded as business state; the transaction still commits.

**Multi-device intent.** A job row represents one device interaction. A
cross-device request (for example, a VLAN across a site's access switches) is a
parent job with one child job per device:

- the parent has `device_id = NULL`, `parent_job_id = NULL`, and the target
  selector in its payload; it is not claimed by a worker;
- each child has the same `job_type`, `parent_job_id` set, and its own
  `device_id`, lock, lease, retry budget, and steps;
- the API creates parent and children plus their outbox events in one
  transaction; children are queued independently;
- the parent becomes `running` when the first child starts and ends `succeeded`
  only when every child succeeds, `failed` when all terminal children failed,
  and `partial` when results are mixed;
- retrying failed children creates new child jobs; it never re-runs successful
  children or duplicates the parent;
- if any target requires approval, the whole parent is held for approval and
  children are created but not published; allocation happens in the approval
  transaction;
- cancelling the parent requests cancellation of every non-terminal child; the
  parent ends `cancelled` only when every child is cancelled, otherwise
  `partial`.

A parent never holds a device lock. This preserves per-device isolation and
prevents one unreachable switch from blocking the whole fabric intent.

#### 8.3 Concurrency and locking

| Race | Control |
| --- | --- |
| Two requests allocate the same IP/VLAN | Fixed-order `SELECT ... FOR UPDATE` on the allocation scope; unique constraints as the final backstop |
| Two workers execute the same job | Atomic claim on device-scoped `automation_jobs` with lease (`device_id IS NOT NULL`; parent rows excluded); Celery duplicate delivery is a no-op |
| Two jobs target the same device | Exclusive `device_locks` row; second job stays queued/retries with backoff |
| Audit overlaps a push | Audit checks for an active exclusive lock and reschedules/skips the device |
| Worker dies mid-push | Lease expires; job requeued; next attempt re-reads live state and compares the rendered hash before pushing |
| Stale worker after lock loss | Worker renews lease/lock before each mutating step and aborts if ownership is lost; no commit after a newer claim |
| Duplicate client request | `Idempotency-Key` + request hash; same key/body returns the original response; different body returns `409 idempotency_key_reused` |
| Retry after ambiguous commit | Adapter reports commit uncertainty; job becomes `failed` with `commit_uncertain` and a compensation/reconciliation job is required; it is not blindly re-pushed |

**SQLite note:** SQLite does not provide row-level locking or `SKIP LOCKED`.
Local development may use a single worker and a process-wide allocation lock;
production concurrency claims require PostgreSQL-backed tests. The milestone
gate for M12/M13 must record PostgreSQL evidence, not SQLite evidence.

#### 8.4 Rendering, pre-flight, push, and verification

**Rendering**

- The worker resolves the device's `template_release` and `template_key` from
  the desired-state API and fetches that exact Git commit/tag. It never renders
  from an unpinned branch.
- Jinja2 uses `SandboxedEnvironment` and `StrictUndefined`. Missing variables
  are a render failure, not blank output.
- The render result has a SHA-256 hash. A second identical render is a no-op;
  identical desired/live hashes short-circuit the push unless `force` is set.
- Output is checked against a per-platform command allowlist/denylist and
  basic structural validation before any device session is opened.
- Templates are trusted code, but they are still reviewed, signed, and tested
  in CI. They have no access to secrets; secrets are substituted by the worker
  at the device-adapter boundary, never rendered into stored snapshots.

**Pre-flight**

The worker verifies, at minimum:

- device is reachable, platform matches the adapter, and credentials resolve;
- the target interface exists and is not claimed by a different managed intent;
- the device's current config hash matches the expected baseline or the job is
  explicitly allowed to proceed on a changed baseline;
- the requested VLAN/IP/subnet still exist and are in a deployable state;
- no conflicting uncommitted config session exists;
- platform VLAN defaults (including VLAN 1/native VLAN) are handled explicitly;
  a job never changes the native VLAN or removes management reachability unless
  that change is the requested intent;
- the requested operation is supported by the adapter's capabilities
  (candidate config, commit-confirm, rollback, etc.).

A failed pre-flight is a non-retryable `preflight_failed` job failure unless the
cause is transient (for example, device timeout).

**Push semantics**

| Platform capability | Preferred behaviour | Fallback |
| --- | --- | --- |
| Candidate config + commit | Load candidate, show diff, commit, verify | — |
| Commit-confirm with rollback timer | Commit with confirmation window; confirm after post-check | Automatic revert if confirmation is not received |
| Config replace / archive rollback | Save pre-change config, replace/merge, verify, keep rollback artifact | Do not apply a blind reverse diff |
| Plain CLI only | Apply explicit, reversible commands; save pre-change snapshot; verify | If a failure occurs, mark `failed`/`commit_uncertain` and require a compensation job; do not guess a rollback |

**Post-check**

A job is successful only after the worker re-reads the relevant running
configuration and verifies the required lines/objects. Exit code alone is not
evidence. The completion payload includes the observed config hash and the
verification result. If verification fails, the job is `failed` with
`post_check_failed`; the resource is not marked `active`.

#### 8.5 Failure semantics

| Situation | Job state | Resource state | Operator action |
| --- | --- | --- | --- |
| Validation/approval rejection | `cancelled` | unchanged | Fix request or re-approve |
| Approval expired | `cancelled` | unchanged | Submit a new request |
| Pre-flight failure | `failed` | `pending_deploy` | Correct intent/device, retry |
| Device unreachable/auth failure | `failed` (retryable until max attempts) | `pending_deploy` | Restore reachability/credentials, retry |
| Render/template failure | `failed` (non-retryable) | `pending_deploy` | Fix template release or intent |
| Push rejected by device | `failed` | `pending_deploy` or `failed` | Inspect step log, correct, retry |
| Ambiguous/partial commit | `failed` (`commit_uncertain`) | `failed` | Audit device, run reconciliation/compensation |
| Post-check failure | `failed` (`post_check_failed`) | `failed` | Inspect diff, remediate via a new job |
| Successful no-op | `succeeded` | `active` | None |
| Successful push + verification | `succeeded` | `active` | None |

**Retry:** an in-flight retryable failure is requeued on the same job with an
incremented attempt. Retrying a terminal job creates a new job with
`retry_of_job_id` set, reuses the payload, and requires a fresh
`Idempotency-Key`; it never reuses the original key or silently reopens the old
job.

**Cross-device failure:** a parent job with mixed child outcomes ends `partial`.
Successful children are **not** automatically rolled back; the operator sees
which devices changed and can request per-child compensation. Automatic
fabric-wide rollback is out of scope for v2.0.

**Cancellation:** queued jobs cancel immediately. A running job receives
`cancel_requested`; the worker cancels only between safe steps. If a commit
already happened, cancellation cannot undo it; the platform records the truth
and offers a compensation job. Resources are released only when the job is
cancelled before any device mutation.

#### 8.6 Provisioning API example

```http
POST /api/v1/automation/jobs HTTP/1.1
Authorization: Bearer <operator-token>
Idempotency-Key: 4e8f4d2a-7c2e-4f4a-a8c1-6d5d0f1b9a10
Content-Type: application/json

{
  "type": "provision_access_port",
  "device_id": 42,
  "interface": "GigabitEthernet1/0/12",
  "intent": {
    "site_id": 3,
    "vlan_id": 120,
    "subnet_id": 88,
    "ip_address": "10.10.20.57",
    "description": "Access link for Sales"
  },
  "options": {
    "dry_run": false,
    "force": false
  }
}
```

```http
HTTP/1.1 202 Accepted
Location: /api/v1/automation/jobs/2f2b5c4e-9a4a-4f57-8c2e-1a0f7d3b6e21
Content-Type: application/json

{
  "job_id": "2f2b5c4e-9a4a-4f57-8c2e-1a0f7d3b6e21",
  "type": "provision_access_port",
  "status": "queued",
  "device_id": 42,
  "links": {
    "self": "/api/v1/automation/jobs/2f2b5c4e-9a4a-4f57-8c2e-1a0f7d3b6e21",
    "steps": "/api/v1/automation/jobs/2f2b5c4e-9a4a-4f57-8c2e-1a0f7d3b6e21/steps"
  }
}
```

A `dry_run: true` job performs pre-flight and read-only collection, then renders
and returns the proposed diff/hash; it never loads a candidate or commits. It
does not transition resource state or retain a reservation. The result is
advisory: a follow-up job revalidates the allocation in its own transaction, so
the proposed IP/VLAN may no longer be free. If the device is unreachable, the
response uses the last verified snapshot and says so. Production policy may
require a successful dry run before an approval is granted.

When approval policy applies, the initial response is
`202` with `status: "pending_approval"`, and no broker task is published until
an authorised approver approves the job. A rejected approval request moves to
`cancelled`; a reaper moves requests past `approval_expires_at` to the same
state and emits `automation.job.approval.expired`. Because no resources were
reserved before approval, there is nothing to release.

### 9 Workflow B — Configuration drift auditing

#### 9.1 Scheduling and fan-out

1. `audit_schedules` holds cron/interval definitions, scope (site, role,
   device list), enabled flag, and `next_run_at`. Timezones are IANA names; each
   due slot is resolved in the schedule's zone and recorded as a UTC instant, so
   DST gaps/overlaps cannot create duplicate runs.
2. The scheduler computes due slots and calls
   `POST /api/v1/internal/audits/runs` with a service token. The run carries
   `schedule_id` and `scheduled_for`.
3. A unique constraint on `(schedule_id, scheduled_for)` guarantees one run per
   due slot even if two scheduler instances race. A manual audit has
   `schedule_id = NULL` and is intentionally independent.
4. The API creates the `audit_run`, fans out one `drift_audit` job per in-scope
   device (each job carries `audit_run_id`), and writes outbox events in the
   same transaction. Per-device jobs isolate failures: one unreachable device
   does not fail the whole sweep.
5. Audit jobs are read-only and do not take the exclusive device lock. If a
   mutating job holds the lock, the audit is rescheduled rather than racing a
   configuration change.
6. When all per-device jobs reach a terminal state, the run is closed with
   counters. A missing/lost child job is detected by the reaper and the run is
   marked `partial`/`failed`, never silently complete.

#### 9.2 Collection and desired state

The audit worker:

- fetches `GET /api/v1/devices/{id}/desired-state` with an `auditor` token
  (inventory read + compliance write only);
- resolves the device's pinned `template_release` and fetches the template from
  Git;
- renders the golden configuration using the same renderer as provisioning
  (one rendering implementation, no drift between the two workflows);
- connects to the device read-only and collects the running configuration with
  paging/terminal-length handling;
- if raw retention is enabled, writes the raw snapshot only to encrypted object
  storage with access audit and a short TTL; otherwise discards it after
  redaction/normalisation. Stores the redacted normalised content plus hashes in
  PostgreSQL.

The desired-state API returns **intent and template binding**, never device
credentials and never a pre-rendered secret-bearing configuration.

#### 9.3 Normalisation pipeline

```
raw live config
   │
   ├─ 1. decode/line-ending normalisation
   ├─ 2. secret redaction (passwords, keys, certificates, SNMP, tokens)
   ├─ 3. volatile-line removal (timestamps, counters, build markers)
   ├─ 4. section parsing (banner, interface, router, ACL, crypto blocks)
   ├─ 5. stable ordering (only for explicitly order-insensitive lists)
   ├─ 6. canonical whitespace/abbreviation rules (per platform profile)
   ├─ 7. fingerprint + unified diff (redacted)
   └─ 8. semantic findings (missing/extra/mismatched objects)
```

Rules are versioned per platform in `normalizers/<platform>.yaml` in Git. A
profile has an explicit version; findings record the profile version and
template release so a rule change is distinguishable from a device change.

Canonical rule categories:

| Category | Examples | Policy |
| --- | --- | --- |
| Volatile lines | `Building configuration...`, `Current configuration : N bytes`, `! Last configuration change`, `ntp clock-period`, `! NVRAM config last updated` | Drop |
| Secret lines | `enable secret`, `username ... secret`, SNMP community, RADIUS/TACACS keys, crypto key material, certificates | Redact; compare keyed hashes when policy requires secret-change detection |
| Platform noise | paging markers, terminal-width artefacts, prompt/echo lines | Drop |
| Order-insensitive lists | NTP servers, name servers, logging hosts, some VLAN lists | Sort only when the platform and template declare the order irrelevant |
| Order-sensitive sections | ACL entries, route-maps, policy-maps, class-maps, crypto maps | Never sort |
| Identity/version lines | OS version/build strings | Exclude from drift; track as device inventory facts |

Normalisation must be line-oriented, deterministic, and cheap. A profile rule
may not execute arbitrary code. Regexes are compiled once at load; pathological
expressions are rejected in CI. Unknown lines are preserved rather than dropped:
preserving an unexpected line can create a finding, while dropping it creates a
false negative.

#### 9.4 Diff, findings, and resolution

- **Unified diff** is for display. It is generated from normalised, redacted
  lines with stable headers.
- **Findings** are generated from section/object-level comparison so line
  shifts do not create churn. Each finding has a fingerprint derived from
  `(device_id, finding_type, stable_object_key, redacted_delta)`.
- One unresolved finding per `(device_id, fingerprint)` exists at a time. A
  repeated drift updates `last_seen_at` and the occurrence count instead of
  creating duplicates.
- A later successful audit that does not reproduce the fingerprint resolves the
  finding (`resolved_at`). An unreachable or errored audit never resolves it.
- Findings carry a `finding_type`: `config_drift` for observed-vs-intent
  differences, or `deployment_gap` when a resource in `pending_deploy`,
  `deploying`, `deprovisioning`, or `failed` is not in the expected state on the
  device. Both are visible and count as non-compliant. A deployment gap is
  suppressed from paging while its provisioning job is non-terminal; after a
  terminal failure it pages as a gap, not as configuration drift. Resources
  with `not_requested` are outside the deployed intent and are not audited.
- Findings carry severity (`critical`, `high`, `medium`, `low`, `info`),
  template release, normaliser version, golden hash, live hash, and the
  audit result. Severity policy is versioned in Git; default is `medium` for an
  unclassified delta.
- Acknowledging a finding suppresses repeat alerts but does not resolve it.
  An `accepted` risk is time-bounded: when `accepted_until` passes, the
  scheduler/reaper reopens it and records an audit event; it is never silently
  resolved.
- **Baseline mode:** the first successful audit of a device records the baseline
  and does not page anyone. Findings are visible, and alerts remain suppressed
  until the baseline is acknowledged or the configured grace window expires.
  This prevents a first-contact alert storm.

#### 9.5 Compliance scoring

Per audit result, a managed device is one of:

- `compliant` — audit succeeded and no unresolved finding was produced;
- `drifted` — audit succeeded and at least one finding is open/acknowledged;
  accepted findings are reported separately, remain visible with their expiry,
  and do not count as drift for scoring;
- `error` — authentication, timeout, adapter, or normaliser failure;
- `unreachable` — device could not be contacted;
- `skipped` — disabled, out of scope, or device busy.

Metrics:

```
compliance_score = compliant / (compliant + drifted) × 100
coverage         = (compliant + drifted) / managed_devices × 100
error_rate       = (error + unreachable) / managed_devices × 100
```

- `managed_devices` excludes `disabled` devices but includes errored/unreachable
  devices in `coverage` and `error_rate`.
- A score of 100% is shown only when coverage is 100% and no errors occurred.
- Weighted rollups use `devices.criticality`; raw counts are always available.
- Trends come from `audit_runs` and `audit_results`, not from mutable dashboard
  counters.
- Compliance must never be computed from a device's last successful audit
  indefinitely. If the last success is older than the configured freshness
  threshold, the device is `stale` for dashboard purposes and excluded from
  "current" compliance claims.

#### 9.6 Alerting, deduplication, and suppression

- The audit completion transaction emits `compliance.drift.detected`,
  `compliance.drift.resolved`, and `compliance.audit.completed` outbox events.
- The notification dispatcher fans out to webhook endpoints filtered by event
  type, resolves secrets from Vault, signs the payload, and records a delivery.
- Deduplication uses the finding fingerprint + open state; a repeated audit does
  not resend the same alert unless the drift has been resolved and re-detected.
- Rate limits and grouping prevent a single template error from paging the
  entire fleet. Grouping is by site/role/device, with a count and a sample.
- Suppression windows are explicit, audited, and time-bounded. "Silence
  forever" is not a supported alert state; risk acceptance belongs on the
  finding (`accepted`) with an expiry/review date.
- Delivery is at-least-once. The receiver must deduplicate using the event ID;
  signatures include a timestamp and a tolerance window.

#### 9.7 False-positive controls

| Control | Evidence required |
| --- | --- |
| Per-platform fixture corpus (golden + live pairs) | Unit tests assert zero drift for equivalent configs and expected drift for known mutations |
| Normaliser profile version recorded per finding | A profile change is visible in the finding metadata |
| Pinned template release per device | A Git commit does not silently redefine desired state |
| Baseline mode | First audit establishes a baseline without paging |
| Section-aware findings | Line shifts do not create new findings |
| Unknown-line preservation | Unexpected device lines become findings, not silent drops |
| Stale-audit handling | Unreachable devices cannot resolve findings or inflate compliance |
| Two-person review of normaliser changes | Git review + template/normaliser CI |

#### 9.8 Remediation (opt-in)

Remediation is a separate `remediate_drift` job that reuses the provisioning
renderer, adapter, pre-flight, device lock, and post-check. It:

- requires an explicit policy enabling remediation for the site/device;
- requires approval for production or critical devices;
- receives the target finding fingerprints and the pinned template release;
- re-audits immediately after the push and resolves only the findings that are
  actually absent;
- never broadens scope beyond the included findings; if the device changed
  unexpectedly, it aborts.

### 10 API and event contracts

#### 10.1 API conventions

- Version prefix remains `/api/v1`. New automation routes are additive.
- Human auth uses the existing bearer JWT. Machine auth uses hashed API tokens
  with scopes; tokens are never accepted from a query string.
- Write requests that create jobs require `Idempotency-Key`. Duplicate keys
  with the same body return the original result; a different body is
  `409 idempotency_key_reused`.
- Errors keep the v1 envelope:
  `{"error": {"code", "message", "details": [...]}}`.
- Pagination, filtering, and sort conventions follow the existing inventory
  endpoints. Large diffs/snapshots are fetched through a dedicated endpoint,
  not embedded in list responses.
- `/api/v1/internal/*` is for the execution plane only, requires an
  `automation:execute`, `audit:execute`, or `compliance:write` scope, and is
  blocked at ingress.

**New endpoint surface (target)**

| Method | Path | Auth/scope | Purpose |
| --- | --- | --- | --- |
| GET/POST | `/sites` | read / `inventory:write` | Site registry |
| GET/PATCH/DELETE | `/sites/{id}` | read / `inventory:write` | Site detail |
| GET/POST | `/vlans` | read / `inventory:write` | Site-scoped VLAN registry |
| GET/PATCH/DELETE | `/vlans/{id}` | read / `inventory:write` | VLAN detail |
| POST | `/subnets/{id}/allocate` | `inventory:write` | Next-available or explicit IP allocation with locking |
| GET/POST | `/devices` | read / `inventory:write` | Device inventory |
| GET/PATCH/DELETE | `/devices/{id}` | read / `inventory:write` | Device detail/lifecycle |
| GET | `/devices/{id}/interfaces` | read | Interface inventory |
| GET | `/devices/{id}/desired-state` | `inventory:read` | Intent + template binding for renderer/auditor |
| GET | `/devices/{id}/compliance` | read | Current status, last audit, findings |
| GET | `/devices/{id}/snapshots` | read (restricted) | Redacted golden/live snapshots |
| GET/POST | `/automation/jobs` | read / `automation:request` | List/create jobs |
| GET | `/automation/jobs/{id}` | read | Job detail |
| GET | `/automation/jobs/{id}/steps` | read | Redacted step timeline |
| POST | `/automation/jobs/{id}/approve` | `automation:approve` | Approve pending job |
| POST | `/automation/jobs/{id}/reject` | `automation:approve` | Reject pending job |
| POST | `/automation/jobs/{id}/cancel` | `automation:request` | Cancel/request cancellation |
| POST | `/automation/jobs/{id}/retry` | `automation:request` | Create a retry job for a terminal failed job |
| GET/POST | `/automation/schedules` | read / `admin` | Audit schedules |
| PATCH/DELETE | `/automation/schedules/{id}` | `admin` | Update/disable schedule |
| GET/POST | `/automation/tokens` | `admin` | Machine token lifecycle |
| DELETE | `/automation/tokens/{id}` | `admin` | Revoke token |
| GET/POST | `/automation/webhooks` | `admin` | Webhook endpoints |
| PATCH/DELETE | `/automation/webhooks/{id}` | `admin` | Update/disable endpoint |
| GET | `/compliance/summary` | read | Coverage-aware score and freshness |
| GET | `/compliance/runs` | read | Audit run history |
| GET | `/compliance/runs/{id}` | read | Run detail/results |
| GET | `/compliance/findings` | read | Filterable finding list |
| POST | `/compliance/findings/{id}/acknowledge` | `compliance:manage` | Acknowledge/accept risk |
| POST | `/internal/jobs/{id}/claim` | `automation:execute` / `audit:execute` | Atomic claim + device lock + lease; scope restricts job type |
| POST | `/internal/jobs/{id}/heartbeat` | `automation:execute` / `audit:execute` | Extend lease |
| POST | `/internal/jobs/{id}/steps` | `automation:execute` / `audit:execute` | Append redacted step |
| POST | `/internal/jobs/{id}/complete` | `automation:execute` / `audit:execute` | Terminal result + snapshots |
| POST | `/internal/audits/runs` | `automation:execute` | Scheduler creates a run + fan-out |
| POST | `/internal/audits/{run_id}/results` | `compliance:write` | Audit result + findings |
| POST | `/internal/snapshots` | `compliance:write` | Store redacted snapshot metadata/content |

**Scope column semantics:** for human JWTs, `read` means any authenticated
role; `inventory:write`, `automation:request`, and `compliance:manage` require
operator or admin; `automation:approve` and `admin` require admin. Machine tokens
must carry the literal scope. The auditor token has `compliance:write` to submit
results but not `compliance:manage`, so it cannot acknowledge or accept risk.

#### 10.2 Desired-state document

The worker receives intent and a template binding, not a rendered config and
not credentials.

```json
{
  "device": {
    "id": 42,
    "hostname": "edge-mcr-01",
    "platform": "cisco_iosxe",
    "vendor": "cisco",
    "role": "edge_switch",
    "site_id": 3,
    "criticality": "high",
    "template_release": "2026.11.1",
    "template_key": "cisco_iosxe/edge_switch"
  },
  "resources": {
    "vlans": [
      {"id": 7, "vlan_id": 120, "name": "SALES", "provisioning_status": "active"}
    ],
    "subnets": [
      {"id": 88, "cidr": "10.10.20.0/24", "gateway": "10.10.20.1", "vlan_ref_id": 7}
    ],
    "interfaces": [
      {
        "name": "GigabitEthernet1/0/12",
        "mode": "access",
        "access_vlan_ref_id": 7,
        "allowed_vlan_refs": []
      }
    ],
    "ip_addresses": [
      {
        "id": 501,
        "address": "10.10.20.57",
        "hostname": "sales-ap-07",
        "interface": "GigabitEthernet1/0/12",
        "provisioning_status": "pending_deploy"
      }
    ]
  },
  "revision": "sha256:6d1f3c0a..."
}
```

`revision` is a hash of the selected intent fields plus the template binding. It
lets the worker detect that the desired state changed between claim and render.

#### 10.3 Event envelope and topology

All outbox events use a versioned envelope:

```json
{
  "event_id": "2f2b5c4e-9a4a-4f57-8c2e-1a0f7d3b6e21",
  "event_type": "automation.job.queued",
  "event_version": 1,
  "destination": "both",
  "occurred_at": "2026-10-27T10:15:00Z",
  "correlation_id": "4e8f4d2a-7c2e-4f4a-a8c1-6d5d0f1b9a10",
  "aggregate": {"type": "automation_job", "id": "2f2b5c4e-..."},
  "data": {"job_id": "2f2b5c4e-...", "job_type": "provision_access_port"}
}
```

Initial event types:

- `inventory.site.changed`, `inventory.device.changed`,
  `inventory.interface.changed`, `inventory.vlan.allocated`,
  `inventory.vlan.released`, `inventory.subnet.allocated`,
  `inventory.ip.allocated`, `inventory.ip.released`
- `automation.job.requested`, `.queued`, `.started`, `.succeeded`, `.partial`,
  `.failed`, `.cancelled`
- `automation.job.approval_requested`, `.approved`, `.rejected`, `.expired`
- `compliance.audit.started`, `.completed`
- `compliance.drift.detected`, `compliance.drift.resolved`
- `compliance.finding.acknowledged`, `compliance.finding.accepted`,
  `compliance.finding.reopened`
- `compliance.score.changed`
- `device.reachability.changed`
- `change_record.created`
- `template.release.promoted`

Delivery semantics: at-least-once, no global ordering, ordered per aggregate
only where the consumer needs it. `destination: both` means the event is
published to the job queue and the notification dispatcher; the two deliveries
are independent and both deduplicate by `event_id`. Event schemas are versioned;
additive fields are preferred, and a breaking change requires a new
`event_version` with a documented consumer migration. After the configured
maximum attempts, an outbox row is marked `dead_lettered_at` and alerted; it is
never silently discarded and can be replayed after the cause is fixed.

**Webhook signing:** `X-NetSpace-Signature: t=<unix>,v1=<hex hmac-sha256>` over
`t + "." + raw_body`. Receivers reject stale timestamps and duplicate event
IDs. Secrets live in Vault and are rotated independently of the endpoint row.

### 11 Security architecture

#### 11.1 Human and machine identity

| Capability | viewer | operator | admin | `auditor` token | `provisioner` token |
| --- | --- | --- | --- | --- | --- |
| Read inventory/reports/compliance | yes | yes | yes | yes | yes |
| Create/cancel provisioning jobs | no | yes | yes | no | yes |
| Approve production remediation/provisioning | no | policy | yes | no | no |
| Manage devices/VLANs/sites | no | yes | yes | no | no |
| Manage tokens/webhooks/schedules | no | no | yes | no | no |
| Submit audit results/findings | no | no | no | yes (`compliance:write`) | no |
| Acknowledge/accept findings | no | yes | yes | no | no |
| Claim/execute internal audit jobs | no | no | no | yes (`audit:execute`) | no |
| Claim/execute internal provisioning jobs | no | no | no | no | yes (`automation:execute`) |
| Read raw snapshots | no | restricted | yes | no | no |

- Human roles remain `viewer`, `operator`, `admin`, enforced server-side.
- Machine tokens carry explicit scopes, an expiry, and a subject; they are not
  users and cannot log in to the UI. Token scopes may include an explicit site
  set, and the API validates resource site membership on every call. Human
  site-scoped roles remain an extension point (open question 6).
- Token storage is a SHA-256 hash plus a short prefix for identification.
  Tokens are shown once at creation, then never recoverable.
- The auditor token is read-only for inventory, claims/executes only
  `drift_audit` jobs, and writes compliance results. It cannot create
  provisioning/remediation jobs, change devices, or read secrets.
- The provisioner token can request/claim jobs but cannot approve its own
  production changes.
- Anonymous read access in v1 is left unchanged for compatibility; all v2
  automation and compliance endpoints require authentication.
- Human SSO is an auth adapter, not a rewrite: an OIDC/SAML provider can map
  IdP groups to `viewer`/`operator`/`admin` while local JWT remains the fallback.
  SSO is not a prerequisite for M12–M16; if required, it lands in M17 identity
  hardening with the same server-side role checks.

#### 11.2 Secrets and device access

- Device rows store `credential_ref` only. Passwords, private keys, SNMP
  communities, and enable secrets are resolved at runtime from Vault/KMS.
- The control plane issues a short-lived Vault token scoped to exactly one
  device credential path; the worker exchanges it only for that
  device's credential. The worker cannot choose a raw Vault path or read another
  device's secret.
- Internal callbacks validate job/run ownership and device scope: a worker
  cannot heartbeat, complete, or submit results for another worker's job or for
  a device outside the claimed run. Credential and desired-state fetches are
  audited by job/device and are never cached or logged.
- Prefer short-lived, per-device or per-role credentials; rotate and revoke
  independently of the IPAM database.
- SSH host-key verification is mandatory. `StrictHostKeyChecking=no` and
  disabled known-hosts checks are not permitted in production.
- Device access uses the OOB management network or a dedicated jump host.
  Workers have egress only to the device management subnet, API, Git, Vault,
  Redis, and (if enabled) encrypted object storage; they have no public internet
  egress by default.
- Secrets are never rendered into stored snapshots or job payloads. The
  renderer produces non-secret configuration; the adapter injects credentials
  into the transport, not the config text.
- Redaction runs before persistence; logs never contain a raw config, a
  password, a token, or a private key.
- Webhook secrets are `secret_ref` values, not endpoint columns.

#### 11.3 Template and supply-chain security

- Templates/normalisers/policies are reviewed in Git, protected by branch
  protection, and promoted by tag/commit. Production only uses pinned releases.
- CI renders fixtures, rejects undefined variables, runs platform structural
  checks, and snapshots expected output. A template change cannot reach
  production without passing these checks.
- Jinja2 runs in a sandboxed environment with no filesystem/network/secret
  access. Custom filters are allowlisted.
- Dependencies and images are pinned/locked, scanned, and accompanied by an
  SBOM. Base images are minimal.
- The template repository is read-only to workers; no runtime process can
  commit a template change.

#### 11.4 Threat model (initial)

| Threat | Mitigation |
| --- | --- |
| Stolen human/API credential | Short expiry, scoped tokens, least privilege, rate limits, anomaly audit, revocation |
| Compromised worker | No DB credentials, read-only Git, scoped Vault policy, egress allowlist, short-lived device credentials |
| Malicious/accidental template | Git review, signed/pinned releases, sandboxed rendering, CI fixtures, command allowlist |
| MITM on device session | SSH host-key verification, TLS/NETCONF, OOB network, no insecure fallback |
| Secret leakage via logs/snapshots | Redaction before persistence, restricted snapshot read, encrypted raw storage, secret scanning in CI |
| Unauthorised config push | RBAC + scopes, approval policy, device lock, pre-flight, audit trail |
| Replay/double execution | Idempotency keys, unique event IDs, atomic claim/lease, rendered-config hash |
| False-negative drift | Fixture corpus, section-aware findings, unknown-line preservation, stale-audit handling, periodic coverage reporting |
| False-positive alert storm | Baseline mode, fingerprint dedupe, grouping/rate limits, profile versioning |
| Webhook SSRF | Endpoint allowlist/egress policy, no redirects, no link-local/metadata targets |
| Database tampering | Least-privilege DB roles, append-only audit convention, PITR, optional hash chain in M17 |
| Denial of service | Body limits, rate limits, queue backpressure, per-site concurrency caps, worker timeouts |

### 12 Reliability, observability, and service targets

#### 12.1 Failure handling

| Failure | Detection | Behaviour |
| --- | --- | --- |
| API replica down | Load balancer health | Other replicas serve; no device state lost |
| PostgreSQL unavailable | Readiness probe, 5xx | API fails closed for writes; workers cannot claim/complete; jobs remain durable |
| Redis/broker unavailable | Queue depth/health | API still commits jobs and outbox rows; relay retries; no lost work |
| Outbox relay down | Outbox lag metric | Backlog grows; alert; replay resumes; consumers idempotent |
| Worker crash | Lease expiry/heartbeat | Reaper requeues with attempt increment; device lock expires; next attempt verifies live state before pushing |
| Device unreachable | Adapter timeout | Retryable with backoff; after max attempts `failed`; device marked `error`/`unreachable` for audit |
| Partial/ambiguous push | Adapter capability + post-check | `commit_uncertain`; no blind re-push or blind rollback; reconciliation/compensation job |
| Git unavailable | Fetch error | Job fails `template_unavailable`; retry; cached template only if its commit hash is verified |
| Vault unavailable | Resolve error | Job fails `credential_unavailable`; no cached-secret fallback |
| Scheduler down | Heartbeat/metric | No new audits; alert; manual audit still available |
| Duplicate broker delivery | Same job ID | Atomic claim/lease makes the second delivery a no-op |
| Duplicate webhook delivery | Receiver dedupe/event ID | Signed at-least-once delivery; receiver deduplicates |
| Clock skew | UTC logs/leases | Session UTC; lease times from a single DB/app clock domain; webhook timestamp tolerance |

#### 12.2 Observability

- **Logs:** structured JSON with `request_id`, `correlation_id`, `job_id`,
  `audit_run_id`, `device_id`, `site_id`, `event_id`, actor/subject, outcome,
  and duration. No secrets or raw config.
- **Metrics:** API latency/error-rate; job creation/queue depth by type;
  job duration/success/failure/retry; outbox lag; lease expiry/requeue; device
  reachability; audit duration; drift findings by severity; compliance
  score/coverage; webhook delivery failures; scheduler lag.
- **Traces:** API → outbox → broker → worker → adapter, with device/site
  attributes. Device sessions are spans, not log dumps.
- **Health:** `/health` remains a liveness endpoint. Add `/ready` for DB plus
  broker reachability. Worker heartbeat/health is separate from API health.
  A degraded broker must not make the API fail liveness.
- **Dashboards/alerts:** job failures, outbox lag, worker absence, device
  unreachable spikes, drift spikes, compliance drops, Vault/Git errors, and
  webhook delivery failures.

#### 12.3 Initial service targets

These are targets to measure, not claims. They are refined during M17.

| Target | Initial objective |
| --- | --- |
| Inventory read API latency | p95 ≤ 300 ms at expected load |
| Job creation API latency (no device I/O) | p95 ≤ 500 ms |
| Job accepted → queued event published | p95 ≤ 2 s |
| Outbox publication lag | p95 ≤ 5 s under normal load |
| Worker heartbeat/lease renewal | ≤ 30 s interval; expired lease detected ≤ 2 intervals |
| Audit scheduling drift | ≤ 60 s from configured slot |
| Job loss | 0 silent losses; every accepted job reaches a terminal state or raises an alert |
| Compliance freshness | Score marked stale after a configurable threshold; no infinite carry-forward |

### 13 Frontend evolution

The UI remains a thin client over the API. It must not render vendor configs,
normalise configs, calculate compliance, or infer job state locally. The new
routes should be route-level code-split so the existing single-chunk constraint
does not grow with Phase 2.

**New routes/pages**

| Route | Content |
| --- | --- |
| `/sites` | Site registry, device/VLAN counts, policy hints |
| `/vlans` | Site-scoped VLAN inventory, allocation state, conflicts |
| `/devices` | Device list: site, role, platform, reachability, compliance |
| `/devices/:id` | Tabs: overview, interfaces, IP assignments, config snapshots, compliance/findings, job history |
| `/automation/jobs` | Job list with type/status/device/time filters |
| `/automation/jobs/:id` | State timeline, redacted steps, dry-run diff, approval/reject/cancel/retry actions |
| `/compliance` | Coverage-aware score, run history, findings (drift vs deployment gaps), dedupe/suppression status |
| `/settings/automation` | Schedules, machine tokens, webhook endpoints, template release pin |
| `/settings/templates` | Current pinned release, manifest status, last validation, promotion link |

**Interaction rules**

- Job status uses polling initially (short interval while active, exponential
  backoff, stop when terminal); move to SSE only if load justifies it.
- Dry-run renders are displayed as a redacted unified diff and labelled with
  whether live config was read in read-only mode or a snapshot was used; they
  never imply that a push occurred.
- Drift pages show finding type (config drift vs deployment gap), golden vs
  live diff, severity, first/last seen, normaliser/template version, and
  resolution evidence.
- Compliance always shows score **and** coverage/error rate; never a bare 100%.
- Actions are hidden/disabled by role, but authorization is enforced by the API.
- Existing Ark UI primitives, dark mode, print styles, and accessibility
  behavior are retained. No new UI framework or state manager is introduced.
- Empty/error/loading states are required for every new page; no hardcoded
  metrics or fake job progress.

### 14 Git configuration repository contract

The configuration repository is separate from the application repository and is
the authority for templates, normalisers, and policy.

```
netspace-config/
  manifest.yaml
  templates/
    cisco_iosxe/
      edge_switch/base.j2
      edge_switch/access_port.j2
    arista_eos/
      edge_switch/base.j2
      edge_switch/access_port.j2
  normalizers/
    cisco_iosxe.yaml
    arista_eos.yaml
  policies/
    approval.yaml
    drift_severity.yaml
    alerting.yaml
  fixtures/
    cisco_iosxe/
      golden/edge_switch.cfg
      live/edge_switch.cfg
    arista_eos/...
  tests/
    render_snapshots/
    normalizer_cases/
```

**Release manifest (illustrative)**

```yaml
schema_version: 1
releases:
  "2026.11.1":
    templates:
      cisco_iosxe:
        edge_switch: templates/cisco_iosxe/edge_switch/base.j2
        access_port: templates/cisco_iosxe/edge_switch/access_port.j2
      arista_eos:
        edge_switch: templates/arista_eos/edge_switch/base.j2
    normalizers:
      cisco_iosxe: normalizers/cisco_iosxe.yaml
      arista_eos: normalizers/arista_eos.yaml
    policies:
      approval: policies/approval.yaml
      drift_severity: policies/drift_severity.yaml
```

**Rules**

- A device references a release (`devices.template_release`), not a moving
  branch. Promotion is an audited operation in the IPAM/UI; it changes the
  device's pinned release and can schedule a provisioning job.
- Templates are rendered only by the execution plane, using the same renderer
  for provisioning and auditing.
- CI validates: manifest schema, template syntax, strict-undefined rendering
  against fixtures, platform command allowlist, normaliser fixture pairs,
  snapshot stability, and secret scanning.
- Commits/tags are signed; the repository is read-only to the worker; no
  runtime process can modify it.
- The app records the release/commit hash in job steps and audit results so a
  finding can be tied to the exact desired-state definition.

### 15 Migration and rollout plan

#### 15.1 Phase mapping

| Phase | Milestone | Outcome |
| --- | --- | --- |
| P0 — blueprint | this document | Agreed architecture, schema, safety invariants, milestones |
| P1 — inventory/identity | M12 | Sites, VLANs, devices, interfaces, service tokens, desired-state read API |
| P2 — durable jobs/events | M13 | Outbox, jobs, locks, leases, scheduler, worker skeleton, observability |
| P3 — provisioning | M14 | Renderer, adapters, pre-flight, safe push, post-check, dry run |
| P4 — drift/compliance | M15 | Scheduled audits, normalisation, diffs, findings, score, alerts |
| P5 — closed loop | M16 | Opt-in remediation, approval workflow, ITSM/alerts, change records |
| P6 — hardening/release | M17 | Secrets/mTLS/OOB hardening, failure injection, performance, DR, runbooks |

#### 15.2 Schema migration rules

1. Add new tables first. Do not rename or drop v1 columns.
2. Add nullable columns with defaults; backfill in batches; add constraints
   after the backfill is verified (separate migration).
3. Backfill sites from distinct non-null `networks.site`,
   `departments.site`, and (later) device data. Preserve the legacy text.
4. Create `vlans` from distinct `(site, vlan_id)` pairs found in subnets and
   departments. Report conflicts where the same site/VLAN has different names
   or multiple networks; never silently choose a winner.
5. Add `subnets.vlan_ref_id` only where the mapping is unambiguous; leave it
   null with an import report otherwise.
6. Populate `interface_ip_assignments` from the legacy `ip_addresses.device`
   text only through a dry-run importer; the legacy text remains the fallback.
   Do not add a second device/interface foreign-key path on `ip_addresses`.
7. Every migration has an upgrade and downgrade. Destructive removal of legacy
   columns requires a separate approved release after the compatibility window.
8. Run migrations against a restored production-like snapshot, measure lock
   time, and provide a rollback/backfill plan before M17.
9. If the current production store is SQLite, M12 includes a rehearsed
   SQLite→PostgreSQL cutover: schema via Alembic, deterministic data
   export/import, sequence reset, row-count and foreign-key reconciliation, and
   a rollback to the pre-cutover backup. Automation concurrency is not enabled
   until the PostgreSQL cutover is verified.

#### 15.3 Execution-plane rollout

- M12/M13: feature-flagged off by default; read-only UI pages may ship.
- M14: dry-run-only in production until adapter/pre-flight evidence is
  certified; then enable for a single canary site/device group.
- M15: monitor-only baseline first; alerts enabled after baseline
  acknowledgement and fixture evidence.
- M16: remediation disabled by default; enable per site/role with approval.
- M17: fleet rollout only after failure-injection, performance, and restore
  drills pass. Rollback is feature-flag disable + worker drain; business data
  remains additive.

#### 15.4 Verification strategy

| Layer | Evidence |
| --- | --- |
| Unit | Calculator/VLSM regression; state machines; renderer; normaliser rules; scoring formula |
| Contract | OpenAPI schemas; desired-state schema; event envelope; webhook signature |
| Integration (PostgreSQL) | Allocation locks, unique constraints, outbox claim/relay, job claim/lease, device lock |
| Device simulation | Fake adapter + recorded fixtures; provisioning success/failure/no-op/ambiguous commit; audit normalization |
| Concurrency | Parallel allocation, duplicate claims, duplicate event delivery, scheduler race |
| Failure injection | Worker kill, broker down, DB down, Git/Vault down, device timeout, partial push |
| Security | Token scope matrix, revocation, redaction, secret scan, SSRF/body limits, host-key policy |
| End-to-end | Simulated fleet: request → job → render → fake push → post-check → audit → finding → alert |
| Performance | Job throughput, audit sweep duration, API latency, outbox lag |

No real production device is required for CI. Real-device validation is a
separate operator-approved gate using a lab or canary site.

### 16 Risks, assumptions, and open questions

#### Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Normalisation false positives/negatives | Alert fatigue or missed drift | Fixture corpus, profile versioning, section-aware findings, baseline mode, unknown-line preservation |
| Unsafe legacy CLI push | Partial config or outage | Candidate/commit where possible; explicit capability matrix; no blind rollback; canary rollout |
| Secret leakage | Credential compromise | Vault refs, runtime resolution, redaction-before-persist, no secrets in logs/configs/jobs, scans |
| Concurrent allocation/push | Duplicate IP/VLAN or device race | Postgres locks, unique constraints, idempotency, device lease, concurrency tests |
| SQLite/production divergence | False confidence | Postgres-only automation tests; SQLite limited to unit/dev |
| Broker/outbox operations | Stuck jobs or duplicate execution | Outbox replay, leases, idempotent consumers, lag alerts |
| Template release drift | Unexpected desired state | Pinned release per device, explicit promotion, CI validation |
| Compliance score gaming | False confidence | Coverage/error rate always displayed; stale audits excluded; no infinite carry-forward |
| Scope creep into an NMS | Delivery risk | Explicit non-goals; adapter/renderer boundary; v2.0 vendor scope limited |
| Device reachability/credential gaps | Audits fail or provisioning blocks | Pre-flight, clear error states, per-device ownership, lab/canary validation |

#### Assumptions

- PostgreSQL is available for production and automation integration tests.
- Redis is available for the Celery broker; broker state is not business state.
- A secrets manager (Vault or cloud equivalent) is available for workers.
- Workers can reach devices over a dedicated OOB/management network.
- Git is reachable read-only by workers, and releases are immutable/pinned.
- Cisco IOS/IOS-XE and Arista EOS cover the first production devices.
- Initial scale is ≤500 managed devices and ≤10,000 interfaces, with design
  headroom to 2,000 devices. Larger fleets require site sharding and queue
  partitioning, reviewed in M17.
- Existing v1 API consumers continue to use the current inventory/plan/report
  contracts; new fields are additive.

#### Open questions (resolve before or during M12/M13)

1. Should machine tokens be issued per worker role (`auditor`, `provisioner`,
   `notifier`) or per deployment instance? Default: per role, rotated on a
   schedule and on incident.
2. Is raw config retention required beyond 7 days for compliance? If yes,
   object storage with legal hold and access audit; otherwise keep redacted
   snapshots only.
3. Which approval policy is required for production: two-person, role-based,
   or ITSM change-ticket correlation? Default: role-based approval by an admin
   plus optional ITSM ticket reference.
4. Which object-storage backend is available (S3/MinIO/none)? If none, raw
   snapshots are not retained; only redacted normalized snapshots are stored.
5. Is a lab/containerlab available for adapter certification, or is the fake
   adapter + canary site the only real-device path?
6. Should site-level RBAC be added in M12 or deferred to M16? Default: site
   scoping fields now, enforcement for automation endpoints in M12, full UI
   scoping later.
7. Do legacy anonymous reads need tightening in v2? Default: no change to v1
   behavior; all new automation/compliance routes require authentication.
8. Is human SSO/OIDC required for v2.0, or does local JWT remain? Default:
   keep local JWT and add an OIDC/SAML adapter in M17 only if required.

---

## Appendix A — Reference DDL for Part II

> Illustrative PostgreSQL reference. Alembic migrations are authoritative.
> SQLite compatibility uses `CHAR(36)` for UUIDs, `JSON` for `JSONB`, and the
> same check constraints. All timestamps are UTC. Add indexes for every foreign
> key and high-selectivity filter used by the API; the DDL below shows only the
> critical operational indexes. Do not copy this DDL into a migration without
> reviewing the project's portability rules.

```sql
-- ---------------------------------------------------------------------------
-- Inventory extensions
-- ---------------------------------------------------------------------------

CREATE TABLE sites (
    id              BIGSERIAL PRIMARY KEY,
    code            VARCHAR(32)  NOT NULL UNIQUE,
    name            VARCHAR(200) NOT NULL UNIQUE,
    address         TEXT,
    timezone        VARCHAR(64)  NOT NULL DEFAULT 'UTC',
    status          VARCHAR(32)  NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'planned', 'retired')),
    created_at      TIMESTAMPTZ  NOT NULL,
    updated_at      TIMESTAMPTZ  NOT NULL
);

CREATE TABLE vlans (
    id                   BIGSERIAL PRIMARY KEY,
    site_id              BIGINT NOT NULL REFERENCES sites(id) ON DELETE RESTRICT,
    vlan_id              INTEGER NOT NULL CHECK (vlan_id BETWEEN 1 AND 4094),
    name                 VARCHAR(200) NOT NULL,
    description          TEXT,
    status               VARCHAR(32) NOT NULL DEFAULT 'active'
                         CHECK (status IN ('active', 'reserved', 'deprecated')),
    provisioning_status  VARCHAR(32) NOT NULL DEFAULT 'not_requested'
                         CHECK (provisioning_status IN (
                             'not_requested', 'pending_deploy', 'deploying', 'active',
                             'failed', 'deprovisioning', 'deprovisioned')),
    created_at           TIMESTAMPTZ NOT NULL,
    updated_at           TIMESTAMPTZ NOT NULL,
    UNIQUE (site_id, vlan_id)
);

CREATE TABLE devices (
    id                  BIGSERIAL PRIMARY KEY,
    hostname            VARCHAR(255) NOT NULL UNIQUE,
    management_ip       VARCHAR(64)  NOT NULL UNIQUE,
    site_id             BIGINT REFERENCES sites(id) ON DELETE RESTRICT,
    device_role         VARCHAR(50)  NOT NULL,
    vendor              VARCHAR(50)  NOT NULL,
    platform            VARCHAR(50)  NOT NULL,
    model               VARCHAR(100),
    serial_number       VARCHAR(100),
    status              VARCHAR(32)  NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'maintenance', 'decommissioned')),
    criticality         VARCHAR(20)  NOT NULL DEFAULT 'medium'
                        CHECK (criticality IN ('low', 'medium', 'high', 'critical')),
    credential_ref      VARCHAR(255),
    template_release    VARCHAR(100),
    template_key        VARCHAR(100),
    config_managed      BOOLEAN NOT NULL DEFAULT FALSE,
    audit_enabled       BOOLEAN NOT NULL DEFAULT FALSE,
    compliance_status   VARCHAR(20) NOT NULL DEFAULT 'disabled'
                        CHECK (compliance_status IN (
                            'unknown', 'compliant', 'drifted', 'error', 'disabled')),
    last_seen_at        TIMESTAMPTZ,
    last_audited_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL,
    CHECK (NOT (config_managed OR audit_enabled) OR credential_ref IS NOT NULL),
    CHECK (NOT (config_managed OR audit_enabled) OR site_id IS NOT NULL),
    CHECK (NOT config_managed OR (template_release IS NOT NULL AND template_key IS NOT NULL)),
    CHECK (status <> 'decommissioned' OR NOT (config_managed OR audit_enabled)),
    CHECK ((audit_enabled AND compliance_status <> 'disabled')
           OR (NOT audit_enabled AND compliance_status = 'disabled'))
);

CREATE TABLE device_interfaces (
    id                    BIGSERIAL PRIMARY KEY,
    device_id             BIGINT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    name                  VARCHAR(100) NOT NULL,
    description           VARCHAR(255),
    if_type               VARCHAR(50),
    mac_address           VARCHAR(32),
    mtu                   INTEGER,
    speed                 BIGINT,
    mode                  VARCHAR(20) NOT NULL DEFAULT 'unset'
                          CHECK (mode IN ('access', 'trunk', 'routed', 'unset')),
    access_vlan_ref_id    BIGINT REFERENCES vlans(id) ON DELETE RESTRICT,
    native_vlan_ref_id    BIGINT REFERENCES vlans(id) ON DELETE RESTRICT,
    admin_status          VARCHAR(20) NOT NULL DEFAULT 'unknown'
                          CHECK (admin_status IN ('up', 'down', 'unknown')),
    oper_status           VARCHAR(20) NOT NULL DEFAULT 'unknown'
                          CHECK (oper_status IN ('up', 'down', 'unknown')),
    last_synced_at        TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL,
    updated_at            TIMESTAMPTZ NOT NULL,
    UNIQUE (device_id, name)
);

CREATE TABLE interface_allowed_vlans (
    interface_id  BIGINT NOT NULL REFERENCES device_interfaces(id) ON DELETE CASCADE,
    vlan_ref_id   BIGINT NOT NULL REFERENCES vlans(id) ON DELETE RESTRICT,
    PRIMARY KEY (interface_id, vlan_ref_id)
);

CREATE TABLE interface_ip_assignments (
    id             BIGSERIAL PRIMARY KEY,
    interface_id   BIGINT NOT NULL REFERENCES device_interfaces(id) ON DELETE RESTRICT,
    ip_address_id  BIGINT NOT NULL REFERENCES ip_addresses(id) ON DELETE RESTRICT,
    role           VARCHAR(20) NOT NULL DEFAULT 'primary'
                   CHECK (role IN ('primary', 'secondary', 'virtual')),
    created_at     TIMESTAMPTZ NOT NULL,
    UNIQUE (interface_id, ip_address_id)
);

ALTER TABLE networks
    ADD COLUMN site_id BIGINT REFERENCES sites(id) ON DELETE SET NULL;

ALTER TABLE departments
    ADD COLUMN site_id BIGINT REFERENCES sites(id) ON DELETE SET NULL;

-- ---------------------------------------------------------------------------
-- Automation job/event backbone
-- ---------------------------------------------------------------------------

CREATE TABLE automation_jobs (
    id                   UUID PRIMARY KEY,
    audit_run_id         UUID,  -- added in M15; FK constrained after audit_runs in the same migration
    parent_job_id        UUID REFERENCES automation_jobs(id) ON DELETE CASCADE,
    retry_of_job_id      UUID REFERENCES automation_jobs(id) ON DELETE SET NULL,
    job_type             VARCHAR(64) NOT NULL
                         CHECK (job_type IN (
                             'provision_access_port', 'provision_vlan', 'deprovision',
                             'config_sync', 'drift_audit', 'remediate_drift')),
    status               VARCHAR(32) NOT NULL DEFAULT 'queued'
                         CHECK (status IN (
                             'pending_approval', 'queued', 'running', 'succeeded',
                             'partial', 'failed', 'cancel_requested', 'cancelled')),
    priority             SMALLINT NOT NULL DEFAULT 100,
    idempotency_key      VARCHAR(128) NOT NULL UNIQUE,
    requested_by         VARCHAR(200) NOT NULL,
    requested_via        VARCHAR(32) NOT NULL DEFAULT 'api',
    device_id            BIGINT REFERENCES devices(id) ON DELETE SET NULL,
    broker_task_id       VARCHAR(200),
    payload              JSONB NOT NULL DEFAULT '{}'::jsonb,
    result               JSONB,
    error_code           VARCHAR(64),
    error_message        TEXT,
    attempts             INTEGER NOT NULL DEFAULT 0,
    max_attempts         INTEGER NOT NULL DEFAULT 3,
    next_attempt_at      TIMESTAMPTZ,
    lease_owner          VARCHAR(200),
    lease_expires_at     TIMESTAMPTZ,
    heartbeat_at         TIMESTAMPTZ,
    approval_status      VARCHAR(20) NOT NULL DEFAULT 'not_required'
                         CHECK (approval_status IN (
                             'not_required', 'pending', 'approved', 'rejected', 'expired')),
    approved_by          VARCHAR(200),
    approved_at          TIMESTAMPTZ,
    approval_expires_at  TIMESTAMPTZ,
    correlation_id       UUID NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL,
    updated_at           TIMESTAMPTZ NOT NULL,
    started_at           TIMESTAMPTZ,
    finished_at          TIMESTAMPTZ
);

CREATE INDEX ix_automation_jobs_status_created
    ON automation_jobs (status, created_at);
CREATE INDEX ix_automation_jobs_device_status
    ON automation_jobs (device_id, status);
CREATE INDEX ix_automation_jobs_audit_run
    ON automation_jobs (audit_run_id);
CREATE INDEX ix_automation_jobs_parent
    ON automation_jobs (parent_job_id);
CREATE INDEX ix_automation_jobs_retry_of
    ON automation_jobs (retry_of_job_id);
CREATE INDEX ix_automation_jobs_lease
    ON automation_jobs (lease_expires_at)
    WHERE status = 'running';

CREATE TABLE automation_job_steps (
    id           BIGSERIAL PRIMARY KEY,
    job_id       UUID NOT NULL REFERENCES automation_jobs(id) ON DELETE CASCADE,
    seq          INTEGER NOT NULL,
    name         VARCHAR(100) NOT NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'skipped')),
    message      TEXT,
    output_redacted TEXT,
    started_at   TIMESTAMPTZ,
    finished_at  TIMESTAMPTZ,
    UNIQUE (job_id, seq)
);

CREATE TABLE outbox_events (
    id              BIGSERIAL PRIMARY KEY,
    event_id        UUID NOT NULL UNIQUE,
    event_type      VARCHAR(100) NOT NULL,
    event_version   INTEGER NOT NULL DEFAULT 1,
    destination     VARCHAR(20) NOT NULL DEFAULT 'jobs'
                    CHECK (destination IN ('jobs', 'notifications', 'both')),
    aggregate_type  VARCHAR(50) NOT NULL,
    aggregate_id    VARCHAR(100) NOT NULL,
    payload         JSONB NOT NULL,
    occurred_at     TIMESTAMPTZ NOT NULL,
    available_at    TIMESTAMPTZ NOT NULL,
    published_at    TIMESTAMPTZ,
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    dead_lettered_at TIMESTAMPTZ,
    correlation_id  UUID
);

CREATE INDEX ix_outbox_unpublished
    ON outbox_events (available_at, id)
    WHERE published_at IS NULL AND dead_lettered_at IS NULL;

CREATE TABLE idempotency_records (
    key             VARCHAR(128) PRIMARY KEY,
    request_hash    CHAR(64) NOT NULL,
    response_status INTEGER NOT NULL,
    response_body   JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL
);

CREATE TABLE device_locks (
    device_id    BIGINT PRIMARY KEY REFERENCES devices(id) ON DELETE CASCADE,
    job_id       UUID NOT NULL REFERENCES automation_jobs(id) ON DELETE CASCADE,
    lock_type    VARCHAR(20) NOT NULL DEFAULT 'exclusive'
                 CHECK (lock_type IN ('exclusive')),
    acquired_at  TIMESTAMPTZ NOT NULL,
    heartbeat_at TIMESTAMPTZ NOT NULL,
    expires_at   TIMESTAMPTZ NOT NULL
);

ALTER TABLE vlans
    ADD COLUMN last_job_id           UUID REFERENCES automation_jobs(id) ON DELETE SET NULL;

ALTER TABLE subnets
    ADD COLUMN vlan_ref_id           BIGINT REFERENCES vlans(id) ON DELETE RESTRICT,
    ADD COLUMN provisioning_status   VARCHAR(32) NOT NULL DEFAULT 'not_requested'
        CHECK (provisioning_status IN (
            'not_requested', 'pending_deploy', 'deploying', 'active',
            'failed', 'deprovisioning', 'deprovisioned')),
    ADD COLUMN last_job_id           UUID REFERENCES automation_jobs(id) ON DELETE SET NULL,
    ADD COLUMN desired_config_hash   CHAR(64),
    ADD COLUMN observed_config_hash  CHAR(64),
    ADD COLUMN last_audited_at       TIMESTAMPTZ;

ALTER TABLE ip_addresses
    ADD COLUMN provisioning_status   VARCHAR(32) NOT NULL DEFAULT 'not_requested'
        CHECK (provisioning_status IN (
            'not_requested', 'pending_deploy', 'deploying', 'active',
            'failed', 'deprovisioning', 'deprovisioned')),
    ADD COLUMN last_job_id           UUID REFERENCES automation_jobs(id) ON DELETE SET NULL;

-- audit_events already exists in v1; extend it rather than creating a second log.
ALTER TABLE audit_events
    ADD COLUMN correlation_id UUID,
    ADD COLUMN job_id         UUID,
    ADD COLUMN source         VARCHAR(32) NOT NULL DEFAULT 'api',
    ADD COLUMN details        JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX idx_audit_events_correlation ON audit_events (correlation_id);
CREATE INDEX idx_audit_events_job ON audit_events (job_id);

-- ---------------------------------------------------------------------------
-- Audit, compliance, and drift
-- ---------------------------------------------------------------------------

CREATE TABLE audit_schedules (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL UNIQUE,
    cron_expression VARCHAR(100) NOT NULL,
    timezone        VARCHAR(64) NOT NULL DEFAULT 'UTC',
    scope           JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at     TIMESTAMPTZ,
    next_run_at     TIMESTAMPTZ,
    created_by      VARCHAR(200) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL
);

CREATE INDEX ix_audit_schedules_due
    ON audit_schedules (next_run_at)
    WHERE enabled = TRUE;

CREATE TABLE audit_runs (
    id              UUID PRIMARY KEY,
    schedule_id     BIGINT REFERENCES audit_schedules(id) ON DELETE SET NULL,
    scheduled_for   TIMESTAMPTZ,
    trigger         VARCHAR(20) NOT NULL
                    CHECK (trigger IN ('scheduled', 'manual')),
    scope           JSONB NOT NULL DEFAULT '{}'::jsonb,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'completed', 'partial', 'failed')),
    devices_total   INTEGER NOT NULL DEFAULT 0,
    devices_compliant INTEGER NOT NULL DEFAULT 0,
    devices_drifted INTEGER NOT NULL DEFAULT 0,
    devices_error   INTEGER NOT NULL DEFAULT 0,
    devices_unreachable INTEGER NOT NULL DEFAULT 0,
    devices_skipped INTEGER NOT NULL DEFAULT 0,
    initiated_by    VARCHAR(200) NOT NULL,
    error           TEXT,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL
);

CREATE UNIQUE INDEX uq_audit_run_schedule_slot
    ON audit_runs (schedule_id, scheduled_for)
    WHERE schedule_id IS NOT NULL;

ALTER TABLE automation_jobs
    ADD CONSTRAINT fk_automation_jobs_audit_run
    FOREIGN KEY (audit_run_id) REFERENCES audit_runs(id) ON DELETE SET NULL;

CREATE TABLE audit_results (
    id                BIGSERIAL PRIMARY KEY,
    audit_run_id      UUID NOT NULL REFERENCES audit_runs(id) ON DELETE CASCADE,
    device_id         BIGINT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    checked_at        TIMESTAMPTZ NOT NULL,
    status            VARCHAR(20) NOT NULL
                      CHECK (status IN ('compliant', 'drifted', 'error', 'unreachable', 'skipped')),
    is_compliant      BOOLEAN,  -- null for error/unreachable/skipped coverage gaps
    golden_hash       CHAR(64),
    live_hash         CHAR(64),
    template_release  VARCHAR(100),
    template_commit   VARCHAR(100),
    normalizer_version VARCHAR(50),
    error_code        VARCHAR(64),
    error_message     TEXT,
    diff_summary      TEXT,
    UNIQUE (audit_run_id, device_id)
);

CREATE TABLE drift_findings (
    id               BIGSERIAL PRIMARY KEY,
    audit_result_id  BIGINT NOT NULL REFERENCES audit_results(id) ON DELETE RESTRICT,
    last_audit_result_id BIGINT REFERENCES audit_results(id) ON DELETE SET NULL,
    resolved_by_audit_result_id BIGINT REFERENCES audit_results(id) ON DELETE SET NULL,
    device_id        BIGINT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    finding_type     VARCHAR(30) NOT NULL DEFAULT 'config_drift'
                     CHECK (finding_type IN ('config_drift', 'deployment_gap')),
    fingerprint      CHAR(64) NOT NULL,
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    severity         VARCHAR(20) NOT NULL DEFAULT 'medium'
                     CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    state            VARCHAR(20) NOT NULL DEFAULT 'open'
                     CHECK (state IN ('open', 'acknowledged', 'accepted', 'resolved')),
    summary          TEXT NOT NULL,
    diff_redacted    TEXT,
    first_seen_at    TIMESTAMPTZ NOT NULL,
    last_seen_at     TIMESTAMPTZ NOT NULL,
    resolved_at      TIMESTAMPTZ,
    acknowledged_by  VARCHAR(200),
    acknowledged_at  TIMESTAMPTZ,
    accepted_until   TIMESTAMPTZ,
    details          JSONB
);

CREATE UNIQUE INDEX uq_drift_finding_unresolved
    ON drift_findings (device_id, fingerprint)
    WHERE state <> 'resolved';

CREATE TABLE change_records (
    id              BIGSERIAL PRIMARY KEY,
    job_id          UUID NOT NULL REFERENCES automation_jobs(id) ON DELETE RESTRICT,
    device_id       BIGINT REFERENCES devices(id) ON DELETE SET NULL,
    actor           VARCHAR(200) NOT NULL,
    approval_status VARCHAR(20) NOT NULL DEFAULT 'not_required'
                    CHECK (approval_status IN ('not_required', 'approved')),
    approved_by     VARCHAR(200),
    redacted_diff   TEXT,
    outcome         VARCHAR(20) NOT NULL
                    CHECK (outcome IN ('succeeded', 'failed', 'partial', 'cancelled')),
    created_at      TIMESTAMPTZ NOT NULL,
    CHECK (approval_status <> 'approved' OR approved_by IS NOT NULL)
);

CREATE INDEX ix_change_records_job
    ON change_records (job_id);
CREATE INDEX ix_change_records_device
    ON change_records (device_id);

CREATE TABLE change_record_findings (
    change_record_id BIGINT NOT NULL REFERENCES change_records(id) ON DELETE CASCADE,
    finding_id       BIGINT NOT NULL REFERENCES drift_findings(id) ON DELETE RESTRICT,
    PRIMARY KEY (change_record_id, finding_id)
);

CREATE TABLE config_snapshots (
    id               BIGSERIAL PRIMARY KEY,
    device_id        BIGINT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    job_id           UUID REFERENCES automation_jobs(id) ON DELETE SET NULL,
    audit_result_id  BIGINT REFERENCES audit_results(id) ON DELETE RESTRICT,
    snapshot_type    VARCHAR(20) NOT NULL
                     CHECK (snapshot_type IN ('golden', 'live')),
    content_redacted TEXT,
    content_sha256   CHAR(64) NOT NULL,
    raw_object_key   TEXT,
    template_release VARCHAR(100),
    template_key     VARCHAR(100),
    template_commit  VARCHAR(100),
    collected_at     TIMESTAMPTZ NOT NULL,
    expires_at       TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL
);

CREATE INDEX ix_config_snapshots_device_time
    ON config_snapshots (device_id, collected_at DESC);

-- ---------------------------------------------------------------------------
-- Machine identity and outbound delivery
-- ---------------------------------------------------------------------------

CREATE TABLE api_tokens (
    id           BIGSERIAL PRIMARY KEY,
    name         VARCHAR(200) NOT NULL,
    subject      VARCHAR(200) NOT NULL,
    token_prefix VARCHAR(16) NOT NULL,
    token_hash   CHAR(64) NOT NULL UNIQUE,
    scopes       JSONB NOT NULL,
    expires_at   TIMESTAMPTZ NOT NULL,
    last_used_at TIMESTAMPTZ,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_by   VARCHAR(200) NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL
);

CREATE TABLE webhook_endpoints (
    id           BIGSERIAL PRIMARY KEY,
    name         VARCHAR(200) NOT NULL,
    url          TEXT NOT NULL,
    secret_ref   VARCHAR(255) NOT NULL,
    event_types  JSONB NOT NULL,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_by   VARCHAR(200) NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL
);

CREATE TABLE webhook_deliveries (
    id               BIGSERIAL PRIMARY KEY,
    endpoint_id      BIGINT NOT NULL REFERENCES webhook_endpoints(id) ON DELETE CASCADE,
    event_id         UUID NOT NULL,
    status           VARCHAR(20) NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'delivered', 'failed', 'dead')),
    attempts         INTEGER NOT NULL DEFAULT 0,
    next_attempt_at  TIMESTAMPTZ,
    last_status_code INTEGER,
    last_error       TEXT,
    created_at       TIMESTAMPTZ NOT NULL,
    delivered_at     TIMESTAMPTZ,
    UNIQUE (endpoint_id, event_id)
);

CREATE INDEX ix_webhook_deliveries_due
    ON webhook_deliveries (next_attempt_at)
    WHERE status IN ('pending', 'failed');
```

**Deliberate omissions from the reference DDL**

- A `vlans.provisioning_status`/`subnets.provisioning_status` value of
  `active` is never inferred from an IPAM write. Only a successful device
  post-check or a successful baseline audit sets it.
- No credential columns exist by design. `devices.credential_ref` is a pointer,
  not a secret.
- Raw config is not a first-class unencrypted column. `config_snapshots` stores
  redacted content and a hash; raw content, if retained, lives in encrypted
  object storage referenced by `raw_object_key`.
- `device_locks` has no `shared` mode because audits are read-only and skip a
  device with an active exclusive lock. A future shared-lock mode can be added
  without changing the provisioning contract.

## Appendix B — Normaliser profile example

Illustrative, not exhaustive. Real profiles ship with fixture tests.

```yaml
profile: cisco_iosxe
version: "1.2.0"

drop_patterns:
  - '^Building configuration\.\.\.$'
  - '^Current configuration : \d+ bytes$'
  - '^! Last configuration change at .*$'
  - '^! NVRAM config last updated at .*$'
  - '^! Startup-config last updated at .*$'
  - '^ntp clock-period \d+$'
  - '^.*\b(uptime|last reset)\b.*$'

redact_patterns:
  - pattern: '^(enable secret) .+$'
    replacement: '\1 <redacted>'
  - pattern: '^(username \S+ (?:secret|password)) .+$'
    replacement: '\1 <redacted>'
  - pattern: '^(snmp-server community) \S+(.*)$'
    replacement: '\1 <redacted>\2'
  - pattern: '^(radius-server key|tacacs-server key) .+$'
    replacement: '\1 <redacted>'

ignore_blocks:
  - start: '^crypto pki certificate chain '
    end: '^\s*quit\s*$'
  - start: '^certificate '
    end: '^\s*quit\s*$'

order_insensitive:
  - match: '^(ntp server|ip name-server|logging host) '
    strategy: lexicographic
  - match: '^vlan (\d+)$'
    strategy: numeric

order_sensitive_sections:
  - '^ip access-list '
  - '^route-map '
  - '^policy-map '
  - '^class-map '
  - '^crypto map '

exclude_from_drift:
  - '^version \d+\.\d+'
  - '^System image file is '
```

Normaliser changes require fixture evidence: an equivalent golden/live pair must
produce an empty diff, and each known mutation must produce the expected
finding fingerprint.

## Appendix C — New API error codes (target)

The v1 envelope is retained. New codes are additive.

| Code | HTTP | Meaning |
| --- | --- | --- |
| `idempotency_key_reused` | 409 | Same key with a different request body |
| `device_busy` | 409 | An exclusive device lock is held by another job |
| `job_not_claimable` | 409 | Job is not queued, or the lease is still valid |
| `approval_required` | 409 | Policy requires approval before execution |
| `job_not_retryable` | 409 | Failure class prohibits retry |
| `template_unavailable` | 409 | Pinned template release cannot be fetched/verified |
| `template_render_failed` | 422 | Strict rendering failed or output validation rejected |
| `credential_unavailable` | 503 | Secrets manager could not resolve a credential |
| `device_unreachable` | 503 | Device connection failed (retryable depending on policy) |
| `preflight_failed` | 422 | Device/intent precondition failed |
| `post_check_failed` | 422 | Device did not converge to the requested state |
| `commit_uncertain` | 409 | Push outcome is ambiguous; reconciliation required |
| `drift_fingerprint_conflict` | 409 | Finding lifecycle conflict |
| `scope_forbidden` | 403 | Token lacks the required scope or site/device scope |
| `token_expired` | 401 | Machine token expired or revoked |
| `webhook_endpoint_invalid` | 422 | URL/event filter/secret reference rejected |

These codes follow the existing domain-error mapping strategy: messages are
safe for clients, internal details stay in server logs, and no stack traces are
returned.

## Appendix D — Design review checklist

Use this checklist before approving implementation of any Part II milestone:

- [ ] Does the change preserve the three-authority model (IPAM intent, Git
      templates/policy, device observed state)?
- [ ] Does the worker remain free of database credentials?
- [ ] Is every new write idempotent or guarded by a unique constraint?
- [ ] Is every device mutation guarded by a device lock and a pre-flight check?
- [ ] Can the operation be dry-run, and is the dry-run path tested?
- [ ] Are failure, cancellation, retry, and ambiguous-commit paths defined?
- [ ] Are secrets excluded from payloads, logs, snapshots, and diffs?
- [ ] Is the new event/API contract versioned and documented?
- [ ] Is a migration additive and reversible, with a backfill report?
- [ ] Are there fixture/fake-adapter tests that do not depend on a real device?
- [ ] Is PostgreSQL concurrency evidence required where locks/leases are used?
- [ ] Does the UI avoid duplicating backend calculations or inventing state?
- [ ] Are compliance scores shown with coverage and freshness?
