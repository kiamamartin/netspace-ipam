# NetSpace IPAM — Backend

FastAPI service that owns **all** IPAM and VLSM computation. The frontend is a
thin client: it never implements competing allocation logic.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env                                  # optional; sensible defaults
alembic upgrade head                                  # create schema (dev also auto-creates on startup)
uvicorn app.main:app --reload --port 8000
```

Interactive API docs: <http://localhost:8000/docs>

## Tests & lint

```bash
pytest -q          # 155 tests: engine, API, invariants, migrations, reports
ruff check .       # lint (E, F, I, W)
```

## Layout

| Path | Purpose |
| --- | --- |
| `app/services/subnet_calculator.py` | Authoritative IPv4/IPv6 subnet math |
| `app/services/vlsm_allocator.py` | Gateway-aware, largest-first aligned first-fit VLSM engine |
| `app/services/ipam_service.py` | All DB mutations; containment/alignment/overlap validation |
| `app/services/report_service.py` | CSV / XLSX / PDF renderers |
| `app/api/v1/` | Thin route handlers |
| `migrations/` | Alembic migrations (`alembic upgrade head`) |
| `tests/` | Unit, API, property-invariant, migration and export tests |

## Configuration

All settings use the `NETSPACE_` prefix (see `.env.example`), e.g.
`NETSPACE_DATABASE_URL`, `NETSPACE_CORS_ORIGINS`, `NETSPACE_ALGORITHM_VERSION`.
