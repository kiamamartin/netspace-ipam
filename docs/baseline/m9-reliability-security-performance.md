# M9 — Reliability, Security, and Performance

> **Authority:** `MILESTONES.md` §M9. This file is the executed evidence record
> for the M9 gate. Evidence assembled and executed 2026-11-05.

## Scope

Concurrency, input abuse, authorization bypass, database failures, query
performance, recovery.

## Deliverables (all exist)

- Automated regression suite — `backend/tests/test_resilience.py`,
  `backend/tests/test_input_abuse.py`, `backend/tests/test_performance.py`
  (new, this gate) plus pre-existing `backend/tests/concurrency/`,
  `backend/tests/test_auth.py`, `backend/tests/test_invariants.py`
- Security findings report — `docs/quality/security-findings.md`
- Performance measurements — `docs/quality/performance-targets.md`
- Recovery procedure — `docs/quality/recovery.md`

## Acceptance criteria evidence

### M9-AC-001 Concurrency tests executed and passing

- `tests/concurrency/` — 3 passed (M7-AC-008 evidence reused)

### M9-AC-002 Input abuse tests executed (malformed, oversized, injection)

- `tests/test_input_abuse.py` (12 passed): broken/empty/wrong-shape JSON
  bodies → structured `422`; SQL-metacharacter payloads through the search
  parameter are inert (rows unchanged); LIKE metacharacters literal;
  oversized single field (5,000 chars vs schema cap) → `422 validation_error`;
  invalid pagination/enums/path segments → `422/401/404`, all enveloped;
  512-department payload → `422`.
- Pre-existing abuse evidence: login rate limiting → `429`
  (`test_login_rate_limited`), 1 MiB body cap → `413`
  (`test_request_body_size_limited`).

### M9-AC-003 Authorization bypass tests executed and passing

- `tests/test_auth.py` role matrix across networks/subnets/departments/
  addresses/plans/users/audit; anonymous write denial on every mutating
  endpoint; admin-only user lifecycle.

### M9-AC-004 Database failure/recovery scenarios tested

- `tests/test_resilience.py` (4 passed): unreachable DB → structured
  `500 internal_error` envelope with no internals leak; same app instance
  serves `200` immediately after recovery (no restart); a commit failure
  leaves zero partial rows; `/health` keeps serving while the DB is down.
- Migration drills (upgrade/downgrade) pinned by `tests/test_migrations.py`.

### M9-AC-005 Query performance measured against defined targets

- `tests/test_performance.py` executes the gate against the documented
  target ceiling set; deviation fails the test.

### M9-AC-006 No unresolved critical/high-severity security findings

- `docs/quality/security-findings.md`: verdict none unresolved; controls
  S-01–S-06 each backed by executed tests; residual risks tracked in the
  register.

### M9-AC-007 Defined performance targets met (documented thresholds)

- `docs/quality/performance-targets.md`: targets defined and observed
  (median-of-5, warm): subnets list 31.6 ms (≤800), dashboard summary
  44.8 ms (≤800), subnet detail 11.7 ms (≤800), CSV export 9.7 ms (≤1500).

## Test results (2026-11-05)

- New files: 17 passed (`test_resilience.py` 4, `test_input_abuse.py` 12,
  `test_performance.py` 1)
- Full backend suite — **223 passed, 0 failed**; `ruff check .` clean

## Files changed

- `backend/app/api/v1/reports.py` — export auth enforcement (M8 closure;
  see `docs/baseline/m8-governance-reporting.md`)
- `backend/tests/test_auth.py` — export-permission regressions
- `backend/tests/test_reports.py` — authenticated export reads
- `backend/tests/test_resilience.py`, `backend/tests/test_input_abuse.py`,
  `backend/tests/test_performance.py` — new M9 gates
- `docs/quality/{security-findings,performance-targets,recovery}.md` — new
- `docs/quality/milestone-status.json` — M8, M9 status: NOT STARTED → PASS
