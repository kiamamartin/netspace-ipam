# NetSpace IPAM — User Guide

This guide covers the operator-facing application (the React UI served on
`:5173` in development and `:8080` in Docker, behind the FastAPI backend on
`:8000`). The full endpoint contract is in [API.md](API.md); how the system is
deployed and operated is in [RUNBOOKS.md](RUNBOOKS.md).

## 1. Accounts and roles

Sign in on the login card with a username and password. Accounts are created by
an administrator (or by the enterprise seed, see [DATA.md](DATA.md)); passwords
are never stored in source control.

| Role | Can do |
| --- | --- |
| `viewer` | Read everything: dashboard, calculator, lists, reports |
| `operator` | `viewer` + create/update inventory and plans (networks, subnets, IP addresses, departments, plan draft/activate/recalculate/archive) |
| `admin` | `operator` + manage users, browse `audit-events`, perform all writes |

Writing while signed in as `viewer` surfaces the backend's `403` as a visible
error; the server enforces every boundary, not just the UI. Six failed logins
from one address inside a minute are rate-limited with `429`.

## 2. Dashboard

The dashboard aggregates the seeded/production dataset: total networks and
tracked IP addresses, overall utilization, plan counts, conflicts and
near-capacity warnings, plus per-network utilization meters and a recent
activity feed. It is the fastest way to see where capacity runs out.

## 3. Calculator (one-off, nothing is stored)

The calculator pages answer stateless questions — no database rows are created
by them and no token-scoped writes happen:

- **Subnet calculator** — enter a CIDR/address (+ prefix or host requirement),
  get network/broadcast/first/last addresses and the usable-range summary.
- **VLSM planner** — a list of departments with host requirements (plus
  optional VLAN, gateway, growth %, reserved addresses) that must fit into one
  parent block. Allocations require the department names; growth is applied to
  the host count; the gateway lands on a usable address. The result view
  mirrors the mandatory example below.
  - Example: `192.168.10.0/24` with 50/25/20/12/10 hosts → `.0/26`,
    `.64/27`, `.96/27`, `.128/28`, `.144/28`, remainder `.160–.255` (96).
- **Split / summarize** — turn one block into `count` equal subnets (or a
  target prefix), or summarize a list of networks into aggregates.
- **Validate** — checks CIDR alignment and no host bits (`422` errors eaten by
  the form show the backend message; the calculator itself normalizes with a
  warning), VLAN and gateway sanity before planning.

## 4. Allocation plans (draft → activate → recalculate → archive)

A plan is a saved VLSM run: the inputs, the computed allocations and the
conflict checks at save time. Plans are `draft` until activated.

- **Create** a plan from the planner (or copy inputs); it's stored as a draft —
  nothing is committed to inventory yet.
- **Activate** commits every subnet of the plan to inventory inside one
  transaction. If a department's allocation now collides with something placed
  after the plan was saved, activation fails with a conflict report and commits
  nothing.
- **Recalculate** re-runs the engine from the stored inputs and re-validates.
- **Archive** retires an eligible plan; archived plans stay queryable.

Report exports (CSV / XLSX / PDF) are available from the plan detail view. Exports
require sign-in as of v1 (`401` otherwise) and always show what was stored at
save/recalculate time, not a re-derivation.

## 5. Networks and subnets

Networks are the parent blocks (e.g. `10.0.0.0/8`-style registries per site or
environment), with environment and lifecycle status. Subnets live inside one
network and must be aligned and non-overlapping — the API returns `409` with a
conflict report otherwise.

Per subnet you can track:

- **Owner, location, purpose, VLAN id, lifecycle status** (`active`,
  `reserved`, `released`).
- **Reserve / release workflow** — reserving holds a subnet for a future
  deployment; release refuses to drop a subnet that still contains tracked
  addresses unless you force it (`force` release is explicit and audited).
- **Utilization** — how many tracked addresses exist within the subnet against
  its usable capacity, rendered as a meter in list and detail views.
- **History** — every create/update/reserve/release on the resource is audited
  and queryable via the History dialog (`GET /subnets/{id}/history`).

Deleting a network that still contains subnets is refused (`409`) — release the
subnets first.

## 6. IP addresses

Track individual addresses within a subnet: status (`assigned`/`reserved`/
`available`), department assignment, owner and location. Registering a
duplicate inside the same subnet is rejected. Reserve/release works the same
way as for subnets; released addresses keep their history for later review.
The IP Addresses page supports filtering by subnet, department and status.

## 7. Departments

Departments are planning units reused by the planner (default host
requirement, default VLAN) and used to group tracked addresses. They can be
created, edited and deleted; deletion is refused while still referenced by
tracked addresses.

## 8. Users and audit (admin)

The Users page lists accounts and lets an admin create users, change roles and
passwords, and deactivate or delete them. Protection is built in: the last
admin account cannot demote or deactivate itself.

The audit log (`/audit-events`, admin only) is the chronological record of who
did what to which resource, filterable by resource type and action.

## 9. Reporting and printing

Every network and every plan can be exported as CSV, XLSX or PDF. CSV exports
carry a metadata preamble; XLSX exports have four sheets (summary, allocations,
remaining space, metadata); PDF is print-oriented. The app's print stylesheet
(print view / PDF from the browser) hides navigation and action chrome and
repeats table headers on every page.

## 10. Accessibility, theming and small screens

- The shell ships with a light and dark theme; your choice persists across
  reloads.
- The mounted UI passes a WCAG 2.x A/AA axe-core automated audit on all pages
  (see `docs/baseline/m11-release-certification.md`); dialogs trap focus, and
  tables wrap under 375 px.

## 11. Where errors are explained

All failures surface as banner/toast messages with a human message from the
backend. Typical codes:

| Code | Meaning |
| --- | --- |
| `401` | Signed out / token expired — log in again |
| `403` | Your role may not do this |
| `409` | Conflict: overlap, duplicate, conflict on plan activation, network not empty, invalid lifecycle transition |
| `422` | Validation: host bits set, misaligned prefix, family mismatch, missing department name |
| `429` | Too many login attempts — wait a minute |

If a message mentions "conflict report", open the referenced resource — the
response `details` array points at the row that collided.
