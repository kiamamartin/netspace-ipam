# M4 Gate Evidence — Backend API and Persistence

Date: 2026-10-23 · Recorded per `MILESTONES.md` §2-M4.
Status after evidence: **PASS** (mirrored in `docs/quality/milestone-status.json`).

## Criteria → evidence (executed 2026-10-23)

| AC | Evidence |
| --- | --- |
| 001 versioned routes | live OpenAPI path list — every route under `/api/v1/` (fetched 200 from `/api/v1/openapi.json`) |
| 002 request/response schemas | pydantic schemas (`app/schemas/`), exercised by all API tests; pydantic validation errors return structured 4xx |
| 003 relational persistence | SQLAlchemy models (`app/models/`) — networks, subnets, ip_addresses, departments, plans, audit_events; SQLite dev DB live with seeded data |
| 004 transactions for related-record operations | plan activation commits all subnets or none (`app/api/v1/allocation_plans.py` service transaction) |
| 005 CRUD endpoints tested and passing | `pytest tests/test_api_calculator.py tests/test_api_inventory.py tests/test_api_plans.py tests/test_reports.py -q` → **61 passed**, exit 0 |
| 006 migrations apply to empty DB and roll back | migration drill on an isolated throwaway DB: `NETSPACE_DATABASE_URL="sqlite:///./m4-drill.db" alembic upgrade head` → `Running upgrade -> 0001, initial schema`, **UPG=0**; `alembic downgrade base` → `Running downgrade 0001 -> , initial schema`, **DOWN=0**; drill DB removed afterwards |
| 007 failed transactions leave no partial saves | `test_plan_activation_conflicts_with_existing_subnet` (conflict → activation rolled back), `test_subnet_create_and_overlap_conflict` (overlap → 409, no partial write) |
| 008 consistent error responses documented | `docs/API.md` documents the `{\"error\":{code,message,details}}` envelope + status conventions (422 / 409 / 404 / 204) |
| 009 API integration tests pass | see 005 — the relative `tests/integration/` directory does not exist; flat tests `test_api_*.py` + `test_reports.py` are the documented equivalent (MILESTONES.md M1 authorized "or documented equivalent") |

## First drill attempt (environmental, repaired)

Running the drill against a Git-Bash `/tmp` URL failed (`sqlite3.OperationalError:
unable to open database file`) because Windows Python cannot resolve the MSYS
`/tmp` mapping inside a SQLite URL. Re-run with a repo-local relative URL
(`sqlite:///./m4-drill.db`), which is also what the project documents for
`NETSPACE_DATABASE_URL`. No code changes were needed; the failure was in the
harness, not the product.

## Known deviations

- `R-01` stands: the *seeded legacy dev DB* still has no `alembic_version` stamp, so
  `alembic upgrade head` against THAT database tries to recreate existing tables and
  fails. The M4-AC-006 criterion is met on genuinely empty databases (verified drill);
  stamping or resetting the dev DB is an operator decision (both backup and seed are
  re-runnable).
- `MILESTONES.md` §4–§7 truncation: does not affect M4 criteria.
- OpenAPI document is served under `/api/v1/openapi.json` (root `/openapi.json` 404);
  recorded here so future gates use the correct URL.
