# M8 — Enterprise Governance and Reporting

> **Authority:** `MILESTONES.md` §M8. This file is the executed evidence record
> for the M8 gate. Evidence assembled 2026-11-05 (functional scope delivered
> with M0–M7; export-permission gap M8-AC-004 found and closed 2026-11-05 —
> exports had no auth dependency; regression pinned by `test_exports_require_authentication`).

## Scope

Audit trails, change history, exports, printable reports, dashboards,
configurable policies.

## Deliverables (all exist)

- Operational dashboards — `frontend/src/pages/Dashboard.tsx` renders
  `GET /api/v1/dashboard/summary` (no hardcoded metrics)
- CSV/PDF/XLSX reports — `app/api/v1/reports.py` + `app/services/report_service.py`
- Audit events and change records — `app/models/audit.py`, emit on every
  stateful write; admin-only `GET /api/v1/audit-events`; per-resource
  `/networks|subnets|ip-addresses/{id}/history` read models

## Acceptance criteria evidence

### M8-AC-001 Record who made material changes and when (audit trail)

- Every write endpoint emits `AuditEvent(resource_type, resource_id, action,
  actor, summary, timestamp)`.
- `test_audit_event_emitted_on_stateful_change`, `test_audit_tracks_user_creation`.

### M8-AC-002 Reports match stored data (verified against DB)

- `test_reports_use_database_data_not_recalculation`: a report is generated,
  the inventory is then changed, and the next export must differ — exports
  render stored rows (plan allocations are frozen at save time).
- `test_plan_exports_match_saved_results`: CSV/XLSX/PDF all reflect the same
  saved allocation result.

### M8-AC-003 Privileged changes traceable

- User-administration lifecycle emits audit events (S-01/S-02 controls in
  `docs/quality/security-findings.md`); `test_audit_tracks_user_creation`.

### M8-AC-004 Export permissions enforced

- **Gap found and closed 2026-11-05**: `app/api/v1/reports.py` registered the
  strict auth dependency router-wide
  (`APIRouter(dependencies=[Depends(get_current_user_strict)])`); anonymous
  export requests receive `401` before resource resolution (no resource
  enumeration), any authenticated role may download.
- Regressions: `tests/test_auth.py::test_exports_require_authentication` and
  `::test_export_permission_enforced_for_unknown_resource`;
  `tests/test_reports.py` was updated to authenticate as admin (the anonymous
  export behavior was the gap).

### M8-AC-005 Dashboards reflect real API data

- `Dashboard.tsx` fetches `/api/v1/dashboard/summary`; summary access for
  operator/viewer is pinned by
  `tests/test_auth.py::test_dashboard_summary_readable_by_non_admin_roles`.
- Headless smoke (M6 evidence): viewer/operator dashboards render without an
  error banner; admin Users page lists seeded accounts.

### M8-AC-006 Printable allocation tables and CSV exports functional

- CSV render + `Content-Disposition` verified for networks and plans
  (`tests/test_reports.py`); print stylesheet hides navigation/actions and
  repeats table headers (frontend, M6–M7 evidence).

### M8-AC-007 PDF exports functional

- `tests/test_network_pdf` / `test_plan_exports_match_saved_results`: `%PDF-`
  magic header, non-trivial size, uncompressed streams containing the CIDRs.

### M8-AC-008 Responsive/accessibility; no internal error leakage

- 375 px mobile layout verified headless (M6 smoke); all error responses use
  the `{error:{code,message,details}}` envelope (`app/core/errors.py`);
  `tests/test_resilience.py` asserts no internals leak on 500s.

## Exit evidence required by roadmap §M8 — coverage

- Report-vs-DB comparison → M8-AC-002 tests above
- Audit event samples → emitted on network creation (AA-02 test) and user
  creation (M5 doc)
- Export permission test output → M8-AC-004 regressions
- Dashboard data source verification → M8-AC-005 (API-driven summary + UI smoke)

## Test results (2026-11-05)

- `tests/test_reports.py` — 9 passed (now authenticated)
- `tests/test_auth.py` — 14 passed (2 new export-permission regressions)
- Full backend suite — **223 passed, 0 failed**; `ruff check .` clean
