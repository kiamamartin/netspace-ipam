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

## 2. Milestone Roadmap (M0–M11)

Each phase depends on successful completion of its prerequisites. Prerequisites must `PASS` before a dependent milestone begins, unless an explicit documented exception is recorded.

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

- [ ] M11-AC-001: All mandatory tests pass (recorded output).
- [ ] M11-AC-002: Accessibility checks pass.
- [ ] M11-AC-003: Documentation reviewed and complete.
- [ ] M11-AC-004: Blockers closed.
- [ ] M11-AC-005: Release evidence complete.
- [ ] M11-AC-006: Release candidate tagged (human identity).
- [ ] M11-AC-007: All final release criteria satisfied (see §7).

**Test command:** `make release-check`

**Exit evidence required:** Test report path, accessibility report, documentation review record, release tag hash, verification evidence archive.

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
