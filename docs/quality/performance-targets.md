# Performance targets — M9 (M9-AC-005, M9-AC-007)

Date: 2026-11-05 · Roadmap: `MILESTONES.md` §M9 · Executed test:
`backend/tests/test_performance.py`

## Defined targets

| Endpoint / scenario | Target ceiling (median) | Observed (median of 5, warm) |
| --- | --- | --- |
| `GET /api/v1/subnets?page=1&page_size=200` (200-row list read model) | ≤ 800 ms | 31.6 ms |
| `GET /api/v1/dashboard/summary` (aggregate read model) | ≤ 800 ms | 44.8 ms |
| `GET /api/v1/subnets/{id}` (detail read model: utilization + tracked counts) | ≤ 800 ms | 11.7 ms |
| `GET /api/v1/reports/networks/{id}/csv` (8-subnet export, authenticated) | ≤ 1500 ms | 9.7 ms |

The asserted gates in `test_performance.py` use these ceilings directly. Ceilings
are deliberately padded (~3x observed) so a shared CI host cannot flake while a
runaway regression (N+1 queries, missing pagination) still fails the gate.

## Environment of record

- OS: Fedora Linux · Python 3.14 · SQLite in-memory (`StaticPool`) via the
  pytest fixture (`conftest.py`).
- Dataset: deterministic seed created through the public API — 8 networks and
  64 subnets (`/27` blocks with gateways), single admin auth context.
- Median of 3 runs in the gate, 5 runs for the numbers above; two untimed
  warm-up calls per route before sampling.
- Known variance: file-backed SQLite and production PostgreSQL will show
  different absolute numbers; the suite validates relative budgets for the
  current engine. Re-baseline when switching to `NETSPACE_DATABASE_URL`
  targets in production.

## Interpretation

- All measured read models are > 10x inside their ceilings.
- The largest observed cost is the dashboard summary (multi-bucket aggregate +
  recent-activity join), still under 50 ms on the seeded dataset.
- Write-path performance was not gated here; concurrency correctness is covered
  by `backend/tests/concurrency/` (M7-AC-008, reused by M9-AC-001).
