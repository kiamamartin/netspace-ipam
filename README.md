# NetSpace IPAM

**Intelligent IP Address Management & VLSM Subnet Planning Platform.**

A full-stack IPAM tool: authoritative backend calculation engine (FastAPI +
SQLAlchemy + Alembic) with a React + TypeScript frontend. Every allocation,
validation and report is computed server-side — the UI is a thin client.

## Features

- **Subnet calculator** — IPv4/IPv6 properties, usable hosts, wildcard,
  class/scope, required-prefix lookups, split and summarize (supernetting) tools.
- **VLSM planner** — largest-first, aligned first-fit allocation with growth
  percentages, reserved addresses, VLANs and **gateway-pinned subnets**;
  preview → save as plan → activate (transactional commit to inventory).
- **IPAM inventory** — networks, subnets, tracked IP addresses, departments;
  containment / alignment / overlap validation on every write, full audit trail.
- **Allocation plans** — saved, recalculatable, previewable plans with
  draft → active → archived lifecycle and conflict detection on activation.
- **Reports** — CSV, Excel (XLSX) and PDF exports plus print-optimized views.
- **Dashboard** — utilization meters, near-capacity warnings, conflict list,
  recent activity.

## Quick start (local development)

Backend (terminal 1):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --port 8000
```

Frontend (terminal 2):

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173 (proxies /api to :8000)
```

Optional — load the realistic enterprise demo dataset (multi-site topology,
VLANs, tracked IPs, plans; backs up and resets the dev DB):

```bash
cd backend && .venv/Scripts/python.exe scripts/seed_enterprise.py
# see docs/DATA.md for what it contains
```

## Quick start (Docker)

```bash
docker compose up --build
# frontend  → http://localhost:8080
# backend   → http://localhost:8000  (docs at /docs)
```

## Verification

```bash
cd backend && pytest -q && ruff check .     # 155 tests, lint clean
cd frontend && npm run build && npm run lint # tsc + vite build, oxlint clean
cd frontend && npm run test:ui              # headless-browser UI smoke test (Edge/Chrome,
                                            # backend + `npm run dev` must be running)
```

## Repository layout

```
backend/            FastAPI app, VLSM engine, Alembic migrations, tests
frontend/           React + TS app (Vite): Ark UI design system, light/dark
                    themes, print stylesheet, oxlint, UI smoke test
docker-compose.yml  One-command stack (backend + frontend + volume)
docs/               API reference, architecture, docs maintenance policy
DELIVERY.md         Delivery report: acceptance criteria & verification
```

See `docs/API.md` for the endpoint reference, `docs/ARCHITECTURE.md` for the
full-stack architecture, and `DELIVERY.md` for the acceptance/verification
report. `docs/README.md` defines how those docs are kept current.
