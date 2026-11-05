# `MILESTONES.md` — Enterprise IPAM Development Roadmap & Release Gates

> **Authority:** This file is the authoritative development roadmap. It is enforced by `AGENTS.md`, supplemented by `knowledge.md` and `edge.md`, and mirrored machine-readably in `docs/quality/milestone-status.json`.
>
> **Operator identity:** `kiamamartin` (configured Git identity). No agent may be attributed as author or co-author.
>
> **Core rule:** A milestone is a **gate**, not a task list. Creating files, writing tests, or running commands does not constitute completion. Only executed verification with recorded evidence may produce a `PASS`.

---

## 1. Release Acceptance Standard

| Status      | Meaning                                                                       |
|-------------|-------------------------------------------------------------------------------|
| **PASS**    | All mandatory criteria verified with evidence.                                |
| **FAIL**    | A mandatory criterion fails, a required test fails, or score is below threshold. |
| **BLOCKED** | Verification impossible (missing dependency, environment, service, prerequisite). |
| **NOT STARTED** | No implementation or evidence.                                            |
| **NOT VERIFIED** | Implementation exists but the criterion has not been checked.             |

**Prohibitions:**

- A high score must never override a failed mandatory criterion.
- Coverage percentage alone does not prove correct behavior.
- The agent must not mark a milestone complete because files were created, commands were attempted, or tests were written.

---

## 2. Milestone Roadmap (M0–M17)

Each phase depends on successful completion of its prerequisites. Prerequisites must `PASS` before a dependent milestone begins, unless an explicit documented exception is recorded.

The roadmap has two phases:

| Phase | Milestones | Outcome |
| --- | --- | --- |
| **Phase 1 — Core IPAM** | M0–M11 | The v1.0 planning, inventory, governance, deployment, and release-certified IPAM |
| **Phase 2 — Closed-Loop Automation** | M12–M17 | Turns the IPAM into an active source of truth with device inventory, durable jobs, automated provisioning, drift auditing, and closed-loop remediation |

Phase 2 is defined in `docs/ARCHITECTURE.md` Part II. Phase 2 work may begin
once M7 (inventory) and M10 (deployment) pass; M11 remains the v1.0 release gate
and is a prerequisite for the Phase 2 release (M17). Phase 2 must not weaken any
Phase 1 gate, endpoint, error shape, or data invariant.

> **Target test contracts:** Phase 2 test paths and commands below describe the
> tests that must exist when the milestone begins. They are not evidence that a
> test exists or passes today. A milestone is complete only after its commands
> are executed and the evidence is recorded. Any milestone that adds or changes
> a frontend route also runs `cd frontend && npm run build && npm run lint` and
> adds the route to the UI smoke suite where the live stack is available.

**Phase boundary notes:**

- M7's site/lifecycle work uses the existing `site` text; M12 upgrades it to
  the `sites` registry with compatibility dual-write. Do not build two site
  models.
- M8's change history covers Phase 1 inventory mutations; M16 `change_records`
  cover automation pushes and link to drift findings. They may share audit
  events but are not the same table.
- M9 and M17 are complementary: M9 certifies v1 concurrency, security, and
  performance; M17 certifies the automation plane and the combined release.
- M10 deploys v1; M17 extends deployment/DR to workers, broker, Git, Vault, and
  OOB access.
- M11 certifies v1.0; M17 certifies the combined v1+v2 release without
  reopening or weakening M11.

---

### M0 — Repository Discovery and Baseline

**Depends on:** none

**Scope:**

- Inspect existing codebase, dependencies, runtime, Git state, and current failures.
- Identify reusable functionality and incompatible dependencies.
- Document verified startup commands.

**Deliverables:**

- Baseline report.
- Architecture map.
- Risk register.
- Verified startup commands.

**Acceptance criteria:**

- [ ] Existing uncommitted changes preserved.
- [ ] Current behavior and failures documented with evidence.
- [ ] Git status captured and recorded.
- [ ] Startup commands executed and output verified.
- [ ] No files overwritten without authorization.

**Test command:** N/A (discovery phase)

**Exit evidence required:** Baseline report path, git status output, executed command outputs.

---

### M1 — Architecture and Engineering Foundation

**Depends on:** M0

**Scope:**

- Establish backend/frontend boundaries, configuration strategy, database approach, schemas, API conventions.

**Deliverables:**

- Architecture document.
- Environment templates (`.env.example`).
- Dependency lockfiles.
- Health endpoint.

**Acceptance criteria:**

- [ ] Clean setup succeeds using documented commands.
- [ ] No secrets committed to source control.
- [ ] Lockfiles present and consistent.
- [ ] Health endpoint responds correctly when executed.
- [ ] Backend and frontend boundaries documented.
- [ ] Configuration loaded from environment, not hardcoded.

**Test command:** `make verify-setup` (or documented equivalent)

**Exit evidence required:** Setup command output, health endpoint response, secret scan result.

---

### M2 — IPv4/IPv6 Subnet Calculation Engine

**Depends on:** M1

**Scope:**

- CIDR parsing, subnet math, usable-address calculations, overlap detection, edge cases.

**Deliverables:**

- Independent, deterministic subnet calculation library.
- Automated test suite.
- Known test-vector fixtures.

**Acceptance criteria:**

- [ ] M2-AC-001: Parse and validate IPv4 and IPv6 CIDR notation.
- [ ] M2-AC-002: Calculate network address, prefix, subnet mask where applicable, address count, first/last addresses, broadcast address for IPv4.
- [ ] M2-AC-003: Handle `/31` point-to-point and `/32` host routes correctly.
- [ ] M2-AC-004: Handle `/127` IPv6 point-to-point and `/128` IPv6 host routes correctly.
- [ ] M2-AC-005: Reject invalid prefixes, malformed addresses, and invalid host requirements.
- [ ] M2-AC-006: Detect containment, overlap, and parent-fit relationships.
- [ ] M2-AC-007: Handle IPv4 `/0` and IPv6 `/0` boundaries without overflow or impractical enumeration.
- [ ] M2-AC-008: Use established networking libraries while retaining application-specific validation.
- [ ] M2-AC-009: Expected values checked against known test vectors and, where appropriate, an independent reference implementation.
- [ ] M2-AC-010: No test passes merely because the implementation agrees with itself.

**Test command:** `pytest backend/tests/unit/test_subnet_calculator.py -v`

**Exit evidence required:** Test output, vector fixture paths, reference-implementation comparison results.

---

### M3 — VLSM Allocation and Optimization

**Depends on:** M2

**Scope:**

- Allocate departmental networks from a base CIDR using host requirements, alignment, and deterministic ordering.

**Deliverables:**

- Optimized allocation engine.
- Allocation table output.
- Explicit failure diagnostics.

**Acceptance criteria:**

- [ ] M3-AC-001: Determine smallest valid prefix for each requested host count.
- [ ] M3-AC-002: Account for network and broadcast addresses for ordinary IPv4 subnets, with explicit `/31` and `/32` exceptions.
- [ ] M3-AC-003: Sort requests appropriately rather than allocating in input order.
- [ ] M3-AC-004: Align every subnet to its correct CIDR boundary.
- [ ] M3-AC-005: Prevent overlap between allocated subnets.
- [ ] M3-AC-006: Ensure every allocation fits within the parent network.
- [ ] M3-AC-007: Detect insufficient address space **before** returning a successful allocation.
- [ ] M3-AC-008: Return structured errors for impossible allocations.
- [ ] M3-AC-009: Produce repeatable results for identical inputs.
- [ ] M3-AC-010: Provide summary of consumed space, remaining space, utilization, and unallocated requirements.

**Mandatory regression scenario:**

| Department      | Required hosts | Expected allocation    |
|-----------------|---------------:|------------------------|
| Administration  | 100            | `/25` — 126 usable     |
| ICT             | 50             | `/26` — 62 usable      |
| Finance         | 25             | `/27` — 30 usable      |
| Management      | 10             | `/28` — 14 usable      |

Base network: `192.168.10.0/24`

- [ ] Allocations are non-overlapping, inside the `/24`, with correct network and broadcast addresses.
- [ ] A set of host requirements that cannot fit is **rejected**.

**Test command:** `pytest backend/tests/unit/test_vlsm_allocator.py backend/tests/regression/test_m3_scenario.py -v`

**Exit evidence required:** Test output, allocation table for the mandatory scenario, rejection test for insufficient capacity.

---

### M4 — Backend API and Persistence

**Depends on:** M3

**Scope:**

- Versioned API endpoints, database models, migrations, validation, transactions, consistent errors.

**Deliverables:**

- Documented API (OpenAPI).
- Persistent projects, networks, allocations, and resource relationships.
- Migration files.

**Acceptance criteria:**

- [ ] M4-AC-001: Version API routes (e.g., `/api/v1/`).
- [ ] M4-AC-002: Validate request and response schemas.
- [ ] M4-AC-003: Persist networks and allocation plans in a relational database.
- [ ] M4-AC-004: Use database transactions for operations modifying related records.
- [ ] M4-AC-005: CRUD endpoints tested and passing.
- [ ] M4-AC-006: Migrations apply cleanly to an empty database and roll back correctly.
- [ ] M4-AC-007: Failed transactions do not leave partially saved allocations.
- [ ] M4-AC-008: Consistent error responses documented.
- [ ] M4-AC-009: API integration tests pass.

**Test command:** `pytest backend/tests/integration/ -v && alembic upgrade head && alembic downgrade base`

**Exit evidence required:** Integration test output, migration output, rollback verification, OpenAPI schema path.

---

### M5 — Authentication and Authorization

**Depends on:** M4

**Scope:**

- Secure login, sessions or tokens, user lifecycle, roles, permissions.

**Deliverables:**

- User administration.
- Protected endpoints.
- Role/permission matrix.
- Security tests.

**Acceptance criteria:**

- [ ] M5-AC-001: Enforce authentication and authorization on the server.
- [ ] M5-AC-002: Separate ordinary users, network operators, and administrators through an explicit permission model.
- [ ] M5-AC-003: Anonymous access denied where required (verified by test).
- [ ] M5-AC-004: Forbidden actions rejected server-side (verified by test).
- [ ] M5-AC-005: Prevent users from reading or changing resources outside their authorized scope.
- [ ] M5-AC-006: Credentials, signing keys, and DB passwords kept out of source control.
- [ ] M5-AC-007: Rate limits and request-size limits implemented for exposed services.

**Test command:** `pytest backend/tests/security/ -v && pytest backend/tests/integration/test_auth.py -v`

**Exit evidence required:** Security test output, permission matrix path, secret scan result.

---

### M6 — Frontend and Operator Workflows

**Depends on:** M5

**Scope:**

- Responsive network forms, subnet calculator, VLSM workspace, tables, validation, useful empty/error states.

**Deliverables:**

- Connected UI for entering requirements, calculating, reviewing, and saving allocations.

**Acceptance criteria:**

- [ ] M6-AC-001: Real API integration works (verified against running backend).
- [ ] M6-AC-002: Loading, error, validation, and empty states verified.
- [ ] M6-AC-003: Mobile layouts verified.
- [ ] M6-AC-004: Frontend does not duplicate authoritative backend calculations.
- [ ] M6-AC-005: Form validation surfaces backend validation errors.
- [ ] M6-AC-006: No placeholder or hardcoded metrics presented as live data.

**Test command:** `npm run test --workspace=frontend && npm run build --workspace=frontend`

**Exit evidence required:** Frontend test output, production build output, manual verification notes for empty/error/mobile states.

---

### M7 — IPAM Inventory and Lifecycle Management

**Depends on:** M6

**Scope:**

- Track address spaces, subnets, allocation states, departments, sites, reservations, utilization.

**Deliverables:**

- Searchable IPAM inventory with ownership, history, and lifecycle controls.

**Acceptance criteria:**

- [ ] M7-AC-001: Create and manage sites, departments, parent networks, and child subnets.
- [ ] M7-AC-002: Track subnet status, owner, purpose, location, and lifecycle state.
- [ ] M7-AC-003: Search and filter by CIDR, department, site, status, ownership.
- [ ] M7-AC-004: Show utilization and remaining capacity.
- [ ] M7-AC-005: Support reservation and release workflows.
- [ ] M7-AC-006: Preserve allocation history when address space changes.
- [ ] M7-AC-007: Detect conflicting reservations and duplicate allocations.
- [ ] M7-AC-008: Concurrent changes cannot silently create conflicting allocations (verified by concurrency test).

**Test command:** `pytest backend/tests/integration/test_inventory.py backend/tests/concurrency/ -v`

**Exit evidence required:** Inventory test output, concurrency test output, history-preservation evidence.

---

### M8 — Enterprise Governance and Reporting

**Depends on:** M7

**Scope:**

- Audit trails, change history, exports, printable reports, dashboards, configurable policies.

**Deliverables:**

- Operational dashboards.
- CSV/PDF reports where supported.
- Audit events and change records.

**Acceptance criteria:**

- [ ] M8-AC-001: Record who made material changes and when (audit trail).
- [ ] M8-AC-002: Reports match stored data (verified against DB).
- [ ] M8-AC-003: Privileged changes traceable.
- [ ] M8-AC-004: Export permissions enforced.
- [ ] M8-AC-005: Dashboards reflect real API data (no hardcoded metrics).
- [ ] M8-AC-006: Printable allocation tables and CSV exports functional.
- [ ] M8-AC-007: PDF exports functional if in release scope.
- [ ] M8-AC-008: Interface responsive, accessible, and free of internal error/stack-trace leakage.

**Test command:** `pytest backend/tests/integration/test_reports.py backend/tests/integration/test_audit.py -v`

**Exit evidence required:** Report-vs-DB comparison, audit event samples, export permission test output, dashboard data source verification.

---

### M9 — Reliability, Security, and Performance

**Depends on:** M8

**Scope:**

- Test concurrency, input abuse, authorization bypass, database failures, query performance, recovery.

**Deliverables:**

- Automated regression suite.
- Security findings report.
- Performance measurements.
- Recovery procedure.

**Acceptance criteria:**

- [ ] M9-AC-001: Concurrency tests executed and passing.
- [ ] M9-AC-002: Input abuse tests executed (malformed, oversized, injection attempts).
- [ ] M9-AC-003: Authorization bypass tests executed and passing.
- [ ] M9-AC-004: Database failure/recovery scenarios tested.
- [ ] M9-AC-005: Query performance measured against defined targets.
- [ ] M9-AC-006: No unresolved critical/high-severity security findings.
- [ ] M9-AC-007: Defined performance targets met (documented thresholds).

**Test command:** `pytest backend/tests/security/ backend/tests/concurrency/ backend/tests/performance/ -v`

**Exit evidence required:** Security findings report, performance measurement report, regression suite output.

---

### M10 — Deployment and Operations

**Depends on:** M9

**Scope:**

- Docker-based deployment, production configuration, migrations, health checks, logs, backups, restoration.

**Deliverables:**

- Reproducible deployment.
- Operator guide.
- Backup/restore scripts.
- Service diagnostics.

**Acceptance criteria:**

- [ ] M10-AC-001: Fresh deployment succeeds from a clean environment using documented instructions.
- [ ] M10-AC-002: Health checks functional.
- [ ] M10-AC-003: Logging configured and verified.
- [ ] M10-AC-004: Backup procedure executed successfully.
- [ ] M10-AC-005: Restore drill executed successfully (demonstrated, not merely documented).
- [ ] M10-AC-006: Service diagnostics documented and verified.

**Test command:** `docker compose up -d && ./scripts/healthcheck.sh && ./scripts/backup-restore-drill.sh`

**Exit evidence required:** Deployment log output, healthcheck output, backup artifact hash, restore verification output.

---

### M11 — Release Certification and Handover

**Depends on:** M10

**Scope:**

- End-to-end acceptance tests, accessibility checks, documentation review, release validation.

**Deliverables:**

- Release candidate.
- Test report.
- API documentation.
- User guide.
- Runbooks.
- Versioned release tag.

**Acceptance criteria:**

- [x] M11-AC-001: All mandatory tests pass (recorded output).
- [x] M11-AC-002: Accessibility checks pass.
- [x] M11-AC-003: Documentation reviewed and complete.
- [x] M11-AC-004: Blockers closed.
- [x] M11-AC-005: Release evidence complete.
- [x] M11-AC-006: Release candidate tagged (human identity).
- [ ] M11-AC-007: All final release criteria in M11 and the Universal
      Milestone Gate (§3) are satisfied.

**Test command:** `make release-check` — executed 2026-11-05
(`docs/baseline/m11-release-certification.md`; all criteria PASS; release
tag: `netspace-v1.0.0-rc1` -> fcc4bfb).

**Exit evidence required:** Test report path, accessibility report, documentation review record, release tag hash, verification evidence archive.

---

**Phase 2 — Closed-Loop Automation (M12–M17)**

Phase 2 turns the v1 IPAM into the control plane described in
`docs/ARCHITECTURE.md` Part II. The execution plane (workers) has no database
credentials; all worker reads/writes go through scoped internal API routes.
Every job is durable, idempotent, observable, and auditable.

### M12 — Automation Inventory and Identity Foundation

**Depends on:** M7, M10 (M11 may run in parallel; M17 requires M11)

**Scope:**

- Add the site registry and site-scoped VLAN registry.
- Add device and interface inventory, IP-to-interface assignments, device
  credential references, template release pins, and compliance status.
- Add hashed, scoped machine tokens for auditor/provisioner/worker identities.
- Add the desired-state read contract used by both automation workflows.
- Backfill legacy `site`/`vlan_id`/`device` text safely; keep v1 fields intact.

**Deliverables:**

- Additive Alembic migrations and a dry-run backfill/import report.
- New inventory and identity API endpoints with OpenAPI contracts.
- Machine-token issue/revoke flow and permission matrix.
- Desired-state API contract and fixtures.
- PostgreSQL cutover/verification runbook (including a SQLite source if
  applicable).
- Tests for migrations, constraints, scopes, and no-secret storage.

**Acceptance criteria:**

- [ ] M12-AC-001: Sites support create/read/update/delete, stable codes, and
      site scoping for devices and VLANs; deletion is blocked while referenced
      by devices or VLANs; legacy network/department `site` text remains
      readable.
- [ ] M12-AC-002: VLANs are unique per site (`site_id`, `vlan_id`); duplicate
      conflicts are reported, never silently deduplicated; deletion is blocked
      while referenced; subnet/VLAN site consistency is validated; legacy
      `subnets.vlan_id` remains writable and is dual-written.
- [ ] M12-AC-003: Devices enforce canonical unique hostname and unique
      management IP; devices/interfaces are validated against their site when
      assigned and against their platform. Devices are inventory-first:
      enabling `config_managed` or `audit_enabled` requires a site and
      credential reference; inventory-only devices report
      `compliance_status = disabled`.
- [ ] M12-AC-004: IP-to-interface assignments are referentially valid; deleting
      an assigned IP or interface is blocked until it is unassigned; legacy
      `ip_addresses.device` remains readable and is dual-written during the
      compatibility window.
- [ ] M12-AC-005: Device rows store only `credential_ref`; no password, key,
      token, community string, or webhook secret exists in the database,
      fixtures, repository, or logs.
- [ ] M12-AC-006: Machine tokens are shown once, stored only as hashes, carry
      explicit scopes/expiry/subject, and can be revoked; an auditor token can
      read inventory and submit compliance data but cannot mutate inventory or
      create jobs.
- [ ] M12-AC-007: `GET /api/v1/internal/desired-state/{device_id}` returns
      intent plus the pinned template binding, and never returns credentials or
      a rendered secret-bearing config.
- [ ] M12-AC-008: Migrations are additive and reversible; a dry-run backfill
      report accounts for unmatched sites, VLAN conflicts, and ambiguous
      interface/device mappings without data loss.
- [ ] M12-AC-009: PostgreSQL is used for constraint/backfill evidence; SQLite
      may be used only for unit-level tests.
- [ ] M12-AC-010: Device/site/VLAN/interface mutations emit audit events with
      actor, correlation ID, and safe details.
- [ ] M12-AC-011: If a SQLite source exists, the PostgreSQL cutover reconciles
      row counts and foreign keys, preserves IDs, and demonstrates rollback to
      the pre-cutover backup; automation is not enabled before this passes.

**Test command:**
`pytest backend/tests/automation/test_inventory_model.py backend/tests/security/test_service_tokens.py -v`
plus the documented migration drill against an empty and a restored
production-like database, and the SQLite→PostgreSQL cutover when applicable.

**Exit evidence required:** Test output, migration upgrade/downgrade output,
backfill report, token scope matrix, OpenAPI schema, secret-scan result.

---

### M13 — Durable Jobs, Events, and Execution Skeleton

**Depends on:** M12

**Scope:**

- Add `automation_jobs` (including parent/child grouping), job steps, outbox
  events, idempotency records, device locks, and the execution-plane
  worker/scheduler skeleton.
- Add transactional outbox relay, Celery/Redis task publication, leases,
  retries/backoff, cancellation, and reaper behaviour.
- Add job/event APIs, internal worker callbacks, health/readiness, metrics, and
  correlation IDs.

**Deliverables:**

- Job API (`POST/GET/cancel/approve/reject/retry`) and redacted step timeline.
- Outbox relay and notification-dispatcher skeletons.
- Celery queues for provisioning, audit, and notifications; scheduler process.
- Worker lease/reaper implementation and operational runbook.
- PostgreSQL concurrency/outage tests.

**Acceptance criteria:**

- [ ] M13-AC-001: Job creation is idempotent. The same key and body returns the
      original job; the same key with a different body returns
      `409 idempotency_key_reused`.
- [ ] M13-AC-002: Domain mutation, job row, and outbox row commit atomically. A
      broker outage leaves durable outbox rows that replay without loss.
- [ ] M13-AC-003: Delivery is at-least-once; duplicate task delivery cannot
      execute a job twice because the atomic claim returns not-claimable.
- [ ] M13-AC-004: A claimed job holds a lease with heartbeat; an expired lease
      is requeued with an incremented attempt, and a dead worker cannot keep
      the lock forever.
- [ ] M13-AC-005: An exclusive device lock serialises mutating jobs; a second
      mutating job is queued/retried, and an audit skips a busy device.
- [ ] M13-AC-006: Retryable failures back off with jitter up to max attempts;
      non-retryable failures are not retried; exhausted jobs are terminal and
      observable.
- [ ] M13-AC-007: The scheduler skeleton computes due slots, emits idempotent
      tasks, and survives restart without duplicate fan-out; audit-specific
      scheduling is certified in M15.
- [ ] M13-AC-008: Job steps, logs, and event payloads are redacted and carry
      `correlation_id`/`job_id`; no secrets appear.
- [ ] M13-AC-009: Health/readiness distinguish API liveness, DB readiness, and
      broker readiness; queue depth, outbox lag, outbox dead-letter count, lease
      expiry, and job success/failure metrics are exposed.
- [ ] M13-AC-010: PostgreSQL-backed tests prove claim/lease/outbox/scheduler
      concurrency; no SQLite-only claim is accepted.

**Test command:**
`pytest backend/tests/automation/test_jobs.py backend/tests/automation/test_outbox.py backend/tests/automation/test_locks.py backend/tests/automation/test_scheduler.py -v`

**Exit evidence required:** Test output, PostgreSQL concurrency evidence,
broker-outage drill, worker-kill/lease-requeue evidence, outbox replay evidence,
metrics/health output.

---

### M14 — Provisioning Renderer and Safe Push Engine

**Depends on:** M13

**Scope:**

- Add the Git template release contract, sandboxed Jinja2 renderer, per-platform
  render fixtures, and the device-adapter interface.
- Implement pre-flight, dry-run, candidate/commit push where supported, explicit
  legacy fallback, post-check verification, and compensation semantics.
- Add the provisioning job type and resource provisioning-state transitions.

**Deliverables:**

- `provision_access_port`/`provision_vlan` job paths (or documented equivalent).
- Renderer with strict undefined variables, hash, command validation, and
  template-release pinning.
- Fake adapter plus Cisco IOS-XE and Arista EOS capability profiles.
- Dry-run diff contract, pre-flight checklist, post-check verification.
- Fake-device integration suite covering success, no-op, failure, retry, and
  ambiguous commit.

**Acceptance criteria:**

- [ ] M14-AC-001: Rendering uses the device's pinned Git release, is
      deterministic, rejects missing variables, and produces a stable output
      hash.
- [ ] M14-AC-002: The adapter contract covers connect, pre-flight, read config,
      load candidate, diff, commit, rollback/compensation, verify, and close;
      fake adapters implement it, and real-driver adapters pass the same
      contract suite against recorded sessions. Live-device certification is
      recorded as an environment blocker, not claimed.
- [ ] M14-AC-003: Pre-flight rejects a missing interface, a conflicting managed
      intent, an unexpected baseline (unless explicitly allowed), an unsupported
      platform, a device that is not config-managed or lacks a template pin, and
      a busy device.
- [ ] M14-AC-004: Dry-run produces a redacted diff and output hash without
      mutating the device, transitioning resource state, or leaking a temporary
      reservation; any read-only session follows the same credential and lock
      rules and is labelled in the result.
- [ ] M14-AC-005: Candidate/commit is preferred where supported; legacy
      fallback is explicit, and blind rollback is not implemented.
- [ ] M14-AC-006: A resource becomes `active` only after the post-check
      re-reads and verifies the required state; exit code alone is insufficient.
- [ ] M14-AC-007: Retrying an already-applied change becomes a verified no-op
      via the rendered/live hash; an ambiguous commit yields
      `commit_uncertain`, not a blind re-push.
- [ ] M14-AC-008: Cancellation before mutation releases reservations; after a
      commit, cancellation records the truth and offers compensation instead
      of pretending to roll back.
- [ ] M14-AC-009: Secrets are resolved at runtime and never appear in job
      payloads, rendered config, steps, logs, or snapshots.
- [ ] M14-AC-010: End-to-end fake-device tests cover success, no-op, pre-flight
      failure, device failure, retry, post-check failure, and ambiguous commit.
- [ ] M14-AC-011: Template changes are validated in CI against fixtures and a
      command allowlist before a release can be pinned.
- [ ] M14-AC-012: Cross-device VLAN intent fans out to per-device child jobs
      with independent locks, retries, and steps; the parent is `succeeded`
      only when every child succeeds and `partial` when results are mixed.
- [ ] M14-AC-013: Rendering and pre-flight handle platform VLAN defaults
      (including VLAN 1/native VLAN) explicitly; they never create an
      unintended native-VLAN mismatch or remove management reachability.
- [ ] M14-AC-014: A requester cannot approve their own production/critical
      provisioning job; approval policy is server-enforced, time-bounded, and
      audited.

**Test command:**
`pytest backend/tests/automation/test_renderer.py backend/tests/automation/test_provisioning.py backend/tests/automation/test_adapters.py backend/tests/automation/test_multidevice.py backend/tests/automation/test_approvals.py -v`

**Exit evidence required:** Test output, renderer hash fixtures, adapter
capability matrix, dry-run transcript, fake-device end-to-end output,
cross-device/partial-failure output, approval-policy output, template CI output.

---

### M15 — Drift Auditor and Compliance Engine

**Depends on:** M14

**Scope:**

- Add scheduled/manual audit runs, per-device audit jobs, read-only config
  collection, redaction/normalisation, section-aware diffs, finding lifecycle,
  compliance scoring, and alert dispatch.
- Add audit/compliance APIs and dashboard read models.
- Establish baseline mode and fixture-driven false-positive controls.

**Deliverables:**

- Audit worker and normaliser profiles with golden/live fixture pairs.
- `audit_schedules`, `audit_runs`, `audit_results`, `drift_findings` APIs.
- Coverage-aware compliance summary and trend data.
- Signed, deduplicated webhook alerts with delivery records.
- UI/API for runs, findings, acknowledgement, and snapshots.

**Acceptance criteria:**

- [ ] M15-AC-001: The auditor token is read-only for inventory, can
      claim/execute only `drift_audit` jobs, and can submit audit results; it
      cannot create provisioning/remediation jobs or mutate devices.
- [ ] M15-AC-002: For every supported platform, equivalent golden/live fixture
      pairs produce zero drift; each documented mutation produces the expected
      finding fingerprint.
- [ ] M15-AC-003: Findings are section-aware and fingerprinted; repeated audits
      update `last_seen_at` instead of duplicating unresolved findings.
- [ ] M15-AC-004: A finding resolves only when a later successful audit no
      longer reproduces its fingerprint; unreachable/errored audits never
      resolve findings.
- [ ] M15-AC-005: Per-device audit failures do not fail the whole run; a lost
      child job yields `partial`/`failed`, never a silent `completed`.
- [ ] M15-AC-006: Baseline mode records the first audit without paging, and
      alerts remain suppressed until acknowledgement or the configured grace
      window expires.
- [ ] M15-AC-007: Compliance displays score, coverage, error/unreachable rate,
      and freshness; a bare 100% is impossible when coverage is incomplete or
      audits are stale.
- [ ] M15-AC-008: Alerts are deduplicated by finding fingerprint, grouped/rate
      limited, signed, retried, and delivery-audited; a failed delivery is
      observable.
- [ ] M15-AC-009: Redacted snapshots and diffs are persisted only after
      redaction; raw config, if retained, is encrypted, access-restricted,
      excluded from the normal API, and expires per policy.
- [ ] M15-AC-010: Dashboard/compliance APIs return real audit data and are
      covered by contract tests; no hardcoded metrics.
- [ ] M15-AC-011: The scheduler creates one audit run per due slot via the
      unique `(schedule_id, scheduled_for)` guard; a manual run is independent
      and duplicate fan-out is impossible.
- [ ] M15-AC-012: Deployment gaps are distinguished from configuration drift;
      they do not page while the provisioning job is non-terminal, and a
      terminal failure pages as a gap rather than as drift.

**Test command:**
`pytest backend/tests/automation/test_normalize.py backend/tests/automation/test_drift.py backend/tests/automation/test_compliance.py backend/tests/automation/test_audit_scheduler.py backend/tests/automation/test_deployment_gaps.py -v`

**Exit evidence required:** Test output, fixture corpus paths, baseline-mode
evidence, scoring/coverage test output, scheduled-slot idempotency evidence,
deployment-gap evidence, webhook delivery evidence, UI smoke evidence, snapshot
redaction scan.

---

### M16 — Closed-Loop Remediation, Approval, and ITSM

**Depends on:** M15

**Scope:**

- Add opt-in remediation jobs that reuse the provisioning renderer/adapter and
  device-lock path.
- Add production/critical-device approval policy, self-approval prevention, and
  change records.
- Add ITSM/alert delivery integration with signed, idempotent webhooks.
- Add post-remediation audit verification and finding resolution.

**Deliverables:**

- `remediate_drift` job flow with explicit finding scope.
- Approval policy enforcement and approval audit trail.
- Change-record linkage: job, finding, device, actor, approval, diff, outcome.
- ITSM/webhook delivery adapter and retry/dead-letter handling.
- Remediation tests with fake devices and a fake webhook receiver.

**Acceptance criteria:**

- [ ] M16-AC-001: Remediation is disabled by default and enabled only per
      site/role/device by policy; the server, not the UI, enforces the policy.
- [ ] M16-AC-002: Production or critical-device remediation requires approval;
      a requester cannot approve their own job.
- [ ] M16-AC-003: Remediation reuses the same renderer, adapter, pre-flight,
      device lock, and post-check path; no second push implementation exists.
- [ ] M16-AC-004: A post-remediation audit verifies the result and resolves only
      findings that are actually absent; unverified findings remain open.
- [ ] M16-AC-005: ITSM/alert webhooks are signed, retried with backoff,
      idempotent by event ID, and observable on failure.
- [ ] M16-AC-006: A change record links the job, finding(s), device, actor,
      approval, redacted diff, and outcome; it is queryable from the API.
- [ ] M16-AC-007: No autonomous remediation path exists; policy tests prove
      that auto-remediation cannot run without explicit enablement and approval
      where required.
- [ ] M16-AC-008: The UI/API shows remediation progress and outcome from real
      job state; no simulated or hardcoded progress.
- [ ] M16-AC-009: A rejected or expired approval changes no resource state and
      leaves the finding unchanged (open/acknowledged); expiry is enforced by a
      reaper and audited, and retrying requires a new request.

**Test command:**
`pytest backend/tests/automation/test_remediation.py backend/tests/automation/test_webhooks.py backend/tests/automation/test_approvals.py -v`

**Exit evidence required:** Test output, approval matrix evidence, fake-device
remediation run, post-remediation audit evidence, webhook delivery/retry
evidence, change-record query output, UI smoke evidence.

---

### M17 — Automation Hardening, Disaster Recovery, and Release

**Depends on:** M11, M16

**Scope:**

- Harden secrets, identity, transport, and OOB access.
- Execute failure injection, concurrency/performance, and restore drills.
- Complete runbooks, threat model, documentation, and release evidence.
- Certify the combined v1 + v2 release without weakening Phase 1 gates.

**Deliverables:**

- Secrets-manager integration evidence and credential-rotation drill.
- Threat model, mTLS/OOB/network-policy verification, and secret scan.
- Failure-injection report (worker, broker, DB, Git, Vault, device, partial
  push, lease expiry).
- Performance report and tested restore procedure.
- Runbooks for provisioning, drift, remediation, compensation, and incidents.
- Versioned Phase 2 release candidate/evidence archive.

**Acceptance criteria:**

- [ ] M17-AC-001: Secret scan is clean; no credentials/keys/tokens exist in the
      database, repository, logs, job payloads, or redacted snapshots; raw
      config, if retained, is encrypted, access-restricted, short-TTL, and
      excluded from the normal API. Credential rotation and revocation are
      demonstrated.
- [ ] M17-AC-002: Threat model is reviewed; SSH host-key verification, TLS,
      OOB routing, network policies, and scoped machine identities are verified.
- [ ] M17-AC-003: Failure-injection scenarios pass: worker kill, broker outage,
      DB outage/recovery, Git/Vault outage, device timeout, partial/ambiguous
      push, and expired lease; no duplicate mutating push occurs.
- [ ] M17-AC-004: Defined performance targets are measured and met or explicitly
      waived with operator approval; job throughput, audit duration, API
      latency, and outbox lag are recorded.
- [ ] M17-AC-005: Backup/restore drill proves job/outbox/audit/finding recovery;
      broker state is rebuilt from the outbox without losing accepted jobs.
- [ ] M17-AC-006: Runbooks for provisioning, drift, remediation,
      compensation/rollback, and incident response are reviewed and executable.
- [ ] M17-AC-007: Phase 1 regression suite still passes; no v1 endpoint,
      error shape, invariant, or migration is weakened.
- [ ] M17-AC-008: All Phase 2 safety invariants (§4) have recorded evidence.
- [ ] M17-AC-009: Release candidate is tagged with the human Git identity and
      includes the evidence archive.

**Test command:** `make automation-release-check` (documented equivalent
acceptable only if every constituent command is recorded).

**Exit evidence required:** Secret-scan output, threat-model record,
failure-injection report, performance report, restore-drill output, runbook
review record, Phase 1 regression output, release tag hash, evidence archive.

---

## 3. Universal Milestone Gate (Definition of Done)

Use **this** checklist for **every** milestone. Do not invent a different standard per phase.

```text
Definition-of-done checklist
[ ]  1. Scope and prerequisites are documented.
[ ]  2. All required deliverables exist and are reviewed.
[ ]  3. Implementation is complete for the milestone scope.
[ ]  4. Automated tests have actually been executed.
[ ]  5. Linting, formatting, and type checks pass where configured.
[ ]  6. Relevant security and compatibility checks pass.
[ ]  7. Existing functionality and unrelated changes are preserved.
[ ]  8. Documentation and setup instructions are updated.
[ ]  9. Git diff contains only intended changes.
[ ] 10. Evidence and a PASS, FAIL, or BLOCKED status are recorded.
```

---

## 4. Phase 2 Automation Safety Invariants

These invariants are mandatory for M12–M17. A violated invariant is a **FAIL**
regardless of test counts or coverage.

1. **No worker database credentials.** The execution plane reads and writes only
   through scoped API routes. A worker with a database URL/credential is a
   release blocker.
2. **No unguarded device mutation.** Every mutating job holds an exclusive
   device lock, passes pre-flight, and performs a post-check. The worker renews
   the lock/lease before each mutating step and aborts if ownership is lost; a
   stale worker must not commit after a newer claim. No direct, best-effort push
   path may bypass this.
3. **No blind rollback.** A failed or ambiguous commit must never be "fixed" by
   replaying a reverse diff that was not verified against the device. Use
   candidate/commit, commit-confirm, a verified rollback artifact, or an
   explicit compensation job.
4. **No false `active` state.** Inventory resources become `active` only after a
   successful post-check or a successful baseline audit. A successful HTTP
   response, adapter exit code, or queued job is not deployment evidence.
5. **No secrets at rest or in logs.** Credentials, keys, tokens, community
   strings, and certificate material never appear in the database, job payloads,
   redacted snapshots/diffs, logs, fixtures, or repository history. Raw config,
   if retained, lives only in encrypted, access-restricted, short-TTL storage
   and is never exposed through the normal API.
6. **No untrusted desired state.** Templates are rendered from a pinned Git
   release with strict variables; a moving branch cannot silently change what a
   device should look like.
7. **No alert without identity.** A drift alert carries a stable fingerprint,
   normaliser version, template release, device/site scope, and audit evidence.
   First audits use baseline mode; repeated audits do not duplicate unresolved
   findings.
8. **No manufactured compliance.** Score is always shown with coverage, error,
   unreachable, and freshness data. Stale or errored devices cannot be excluded
   to produce 100%.
9. **No silent job loss.** Every accepted job reaches a terminal state or raises
   an operational alert. Outbox replay, lease expiry, and duplicate delivery
   behaviour must be demonstrated.
10. **No untested concurrency claim.** Locks, leases, unique constraints, and
    outbox claims require PostgreSQL-backed evidence. SQLite-only evidence does
    not certify M12–M17 concurrency.
11. **No autonomous remediation.** Remediation is opt-in, policy-gated, and
    approval-gated where required. No timer or drift event may push a change
    without an explicit enabled policy and the required approval.
12. **No v1 regression.** Existing endpoints, error envelopes, invariants,
    migrations, reports, and Phase 1 gates remain intact. Additive compatibility
    is the default; a breaking change requires explicit operator authorization.

### Phase 2 gate evidence checklist

```text
[ ]  1. PostgreSQL concurrency evidence for locks, leases, outbox, and scheduler.
[ ]  2. Fake adapter plus golden/live fixture corpus; no real-device CI dependency.
[ ]  3. Idempotency/replay evidence for API requests, events, and job retries.
[ ]  4. Failure-injection evidence for worker, broker, DB, Git, Vault, device, and partial push.
[ ]  5. Secret scan and redaction evidence for logs, payloads, snapshots, and diffs.
[ ]  6. State-machine tests for job, resource, finding, and compliance transitions.
[ ]  7. OpenAPI and event-schema contract tests.
[ ]  8. Migration upgrade/downgrade plus backfill dry-run evidence.
[ ]  9. UI verification that backend calculations/state are not duplicated.
[ ] 10. Phase 1 regression suite and v1 compatibility evidence.
```
