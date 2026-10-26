# M5 — Authentication and Authorization

> **Authority:** `MILESTONES.md` §5. This file is the executed evidence record for the M5 gate.

## Scope

Secure login, sessions or tokens, user lifecycle, roles, permissions.

## Deliverables (all exist)

- User administration — `backend/app/api/v1/auth.py` (CRUD, admin-only)
- Protected endpoints — `backend/app/api/deps.py` (`require_operator`, `require_admin`)
- Role/permission matrix — `backend/app/core/security.py` (`ROLE_PERMISSIONS`, `USER_ROLES`)
- Security tests — `backend/tests/test_auth.py`

## Permission matrix (enforced server-side)

| Role       | Read inventory/plans | Write inventory/plans | User administration | Audit events |
|------------|---------------------|----------------------|---------------------|--------------|
| anonymous  | ✓ (no token needed) | ✗ (401)             | ✗ (401)            | ✗ (401)     |
| viewer     | ✓                   | ✗ (403)             | ✗ (403)            | ✗ (403)     |
| operator   | ✓                   | ✓                    | ✗ (403)            | ✗ (403)     |
| admin      | ✓                   | ✓                    | ✓                   | ✓            |

## Acceptance criteria evidence

### M5-AC-001: Enforce authentication and authorization on the server

- `backend/app/api/deps.py`: `get_current_user` resolves bearer tokens; `require_role` factory enforces role checks with 401 (unauthenticated) and 403 (forbidden) responses.
- All mutating endpoints depend on `require_operator` or `require_admin`.

### M5-AC-002: Separate ordinary users, network operators, and administrators

- `USER_ROLES = ("viewer", "operator", "admin")` in `backend/app/core/security.py`
- `ROLE_PERMISSIONS` maps each role to its permission tuple.
- User model carries `role` column with CHECK constraint (migration `0002_users.py`).

### M5-AC-003: Anonymous access denied where required (verified by test)

`test_anonymous_write_denied` asserts 401 for every mutating endpoint without a token:

- POST/PATCH/DELETE networks
- POST/PATCH/DELETE subnets
- POST/PATCH/DELETE departments
- POST/PATCH/DELETE IP addresses
- POST/PATCH allocation plans, POST activate/recalculate/archive
- GET/POST/PATCH/DELETE user administration
- GET audit events

### M5-AC-004: Forbidden actions rejected server-side (verified by test)

`test_role_matrix_on_idempotent_write` asserts operator can write while viewer gets 403 across networks, subnets, departments, IP addresses, and allocation plans (create, update, delete, activate, recalculate, archive). Viewer retains read access throughout.

### M5-AC-005: Prevent users from reading or changing resources outside their authorized scope

- `test_user_administration_admin_only`: operator and viewer get 403 on user CRUD and audit events; only admin can access them.
- `test_audit_events_admin_only`: admin reads audit events (200); operator and viewer get 403.
- Audit events endpoint gated with `require_admin` in `backend/app/api/v1/dashboard.py`.

### M5-AC-006: Credentials, signing keys, and DB passwords kept out of source control

- `backend/.env` is untracked; `.env.example` documents required variables.
- `backend/app/core/security.py` reads `NETSPACE_AUTH_SECRET` from environment; falls back to per-process random secret (dev only, with warning).
- No secrets in source files.

### M5-AC-007: Rate limits and request-size limits implemented for exposed services

- `test_login_rate_limited`: 6th login attempt from a dedicated IP returns 429.
- `test_request_body_size_limited`: 1 MiB+ request body returns 413.

## Test results

### Auth tests (11 passed)

```
tests/test_auth.py::test_health_and_reports_readable_anonymously PASSED
tests/test_auth.py::test_anonymous_write_denied PASSED
tests/test_auth.py::test_invalid_tokens_rejected PASSED
tests/test_auth.py::test_role_matrix_on_idempotent_write PASSED
tests/test_auth.py::test_user_administration_admin_only PASSED
tests/test_auth.py::test_last_admin_self_removal_blocked PASSED
tests/test_auth.py::test_audit_events_admin_only PASSED
tests/test_auth.py::test_login_rate_limited PASSED
tests/test_auth.py::test_request_body_size_limited PASSED
tests/test_auth.py::test_audit_event_emitted_on_stateful_change PASSED
tests/test_auth.py::test_audit_tracks_user_creation PASSED
```

### Full suite

- `test_api_inventory.py` — 22 passed (admin token fixture; audit-events now admin-only)
- `test_api_plans.py` — 9 passed
- `test_reports.py` — 9 passed
- **Total: 191 passed, 0 failed**

## Files changed

- `backend/app/api/v1/dashboard.py` — audit-events endpoint now requires `require_admin`
- `backend/tests/test_auth.py` — expanded `test_anonymous_write_denied`, `test_role_matrix_on_idempotent_write`, `test_user_administration_admin_only`; added `test_audit_events_admin_only`
- `docs/quality/milestone-status.json` — M5 status: NOT STARTED → PASS

## Definition of done

1. ✓ Scope and prerequisites documented.
2. ✓ All required deliverables exist and are reviewed.
3. ✓ Implementation is complete for the milestone scope.
4. ✓ Automated tests have actually been executed (191 passed).
5. ✓ Linting passes (`ruff check .`).
6. ✓ Relevant security checks pass (secret scan clean).
7. ✓ Existing functionality and unrelated changes are preserved.
8. ✓ Documentation updated (this file, milestone-status.json).
9. ✓ Git diff contains only intended changes.
10. ✓ Evidence and PASS status recorded.
