# Recovery procedure — M9 deliverable (M9-AC-004)

Date: 2026-11-05 · Roadmap: `MILESTONES.md` §M9

## 1. Database unavailable at request time

Behavior (verified by `backend/tests/test_resilience.py`):

- every request touching the database returns
  `500 {"error":{"code":"internal_error","message":"An unexpected internal
  error occurred","details":[]}}` — no stack traces or driver internals are
  exposed;
- `/health` keeps serving;
- when the database returns, the application serves traffic again without a
  restart (`test_api_recovers_after_db_failure_without_restart`).

Operator action: check the database server / `NETSPACE_DATABASE_URL`, then
verify with `curl -H "Authorization: Bearer <token>" http://<api>/api/v1/networks`
returning `200`.

## 2. Failed write (crash mid-transaction)

- A commit failure leaves **nothing** persisted
  (`test_failed_commit_leaves_no_partial_state`); partial-success is
  structurally impossible for plan activation, which commits inside one
  transaction (`tests/test_api_plans.py` conflict-rollback cases).
- No operator repair is required after a 500 caused by a database fault:
  the failed request's session is closed without commit.

## 3. Backup and restore (single-node deployment)

- SQLite (default): stop or quiesce writes, copy `backend/netspace.db`
  (the enterprise seed already creates a timestamped copy of the file before
  any reset — see `backend/scripts/seed_enterprise.py`).
- PostgreSQL or any SQLAlchemy URL: use the database's native dump tool
  (`pg_dump`/`restore`), or `alembic` in combination with backups.
- Restore = stop the API process, replace/open the restored database file,
  start the process, verify `/health` returns `200` with `status: ok` and a
  read endpoint returns `200`. (Note: `/health` reports connectivity of the
  configured engine family, not a probe; an unreachable database shows as
  `500` on data endpoints — see §1.)

## 4. Schema migration recovery

- `alembic upgrade head` applies the current schema; `alembic downgrade base`
  reverses it (both drilled on an isolated empty database by
  `backend/tests/test_migrations.py`, exit evidence recorded under M4).
- If an environment started from a legacy database outside Alembic
  management, follow R-01: recreate from seed or stamp a known revision —
  do not hand-edit migration history.
