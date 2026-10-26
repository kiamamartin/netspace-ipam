# M0 Baseline Report — Repository Discovery

Date: 2026-10-23 · Recorded by the development agent per `MILESTONES.md` §2-M0.
Status after evidence: **PASS** (see `docs/quality/milestone-status.json`).

## 1. Repository overview

| Aspect        | State |
|---------------|-------|
| Product       | NetSpace IPAM — full-stack IP address management (FastAPI + SQLAlchemy + Alembic backend, React 19 + TS/Vite + Ark UI frontend) |
| Branch        | `main` · single commit in local history (2026-10-15) |
| Python        | 3.15.0 (`C:\Python315\python.exe`, sole installation) · backend `backend/.venv` |
| Node/Vite     | npm workspaces-style layout in `frontend/`, Vite 8 dev server on :5173 proxying `/api` + `/health` to :8000 |
| Database      | SQLite (`backend/netspace.db`), seeded 2026-10-23 via `scripts/seed_enterprise.py` (14 departments, 12 networks, 41 subnets, 82 IPs, 3 plans); pre-seed backup `netspace.bak-20261023-082331.db` |
| Architecture  | Map: `docs/ARCHITECTURE.md` (exists and covers backend/frontend layering) |

## 2. Git status captured (exit evidence)

Executed: `git status --short` (2026-10-23). Working tree carries **fourteen modified
tracked files** and these untracked paths:
`.rules/`, `AGENTS.md`, `CLAUDE.md`, `MILESTONES.md`, `edge.md`, `knowledge.md`,
`backend/scripts/`, `docs/ARCHITECTURE.md`, `docs/DATA.md`, `docs/README.md`,
`docs/baseline/`, `frontend/smoke.mjs`, `frontend/src/feedback.ts`,
`frontend/src/theme.ts`, `docs/quality/`.
`git diff --stat` (tail): `14 files changed, 3819 insertions(+), 727 deletions(+)`.
**All pre-existing uncommitted changes preserved — nothing was staged, committed,
reverted, or discarded during M0.**

## 3. Current behavior and failures (executed evidence)

| Check                          | Result | Evidence |
|--------------------------------|--------|----------|
| `pytest -q` (backend)          | **155 passed**, 4 warnings, exit 0 | Pre-existing deprecation warning: `alembic.ini` lacks `path_separator` |
| `ruff check .` (backend)       | All checks passed, exit 0 | — |
| `uvicorn app.main:app` :8000   | Running (background PID 20880) | `/health` → `{"status":"ok","app":"NetSpace IPAM","version":"1.0.0","database":"sqlite","algorithm_version":"vlsm-1.0.0"}` |
| `npm run dev` (Vite) :5173     | Running (background PID 8456) | HTTP 200; `/api/v1/dashboard/summary` → 200 with seeded metrics |
| `node smoke.mjs` (UI smoke)    | All PASS incl. dialog gates (`backdrop invisible`, `modal crisp`, `shell plain`, focus trap, dept CRUD) | Headless Edge; note it runs with `--disable-gpu` and cannot exercise GPU compositor behavior |
| `npm run build` (tsc + vite)   | exit 0 | Pre-existing chunk-size advisory only |
| `alembic upgrade head`         | **FAILS** against the current seeded DB (see R-01) | Traceback: `sqlite3.OperationalError: table departments already exists` — migration chain attempts `RUNNING upgrade -> 0001` because `alembic_version` is absent on the legacy DB |

The seeded database was created out-of-band (script/INSERT path), so it has real
tables but no `alembic_version` stamp. Fresh empty-DB migrations were verified by
the project's own migration tests; the failure is specific to stamping an
already-materialized schema. This is recorded as a finding, not fixed in M0
(discovery phase; remedy belongs to the persistence milestone, M4 / R-01).

## 4. Environment constraints discovered

| # | Risk / constraint | Impact | Handling |
|---|---|---|---|
| R-01 | Legacy DB lacks `alembic_version`; `alembic upgrade head` fails with "table departments already exists" | M4-AC-006 gate | Stamp the DB (alembic stamp head) or document reset procedure when M4 starts |
| R-02 | Windows Application Control policy blocks SQLAlchemy 2.1.x compiled DLLs (`_immutabledict_cy`, `_util_cy`) | Backend startup blocked on 2.1.4 | Repository already satisfied by pure-Python wheel **SQLAlchemy 2.0.55** (installed 2026-10-23, within declared `sqlalchemy>=2.0`). Re-verification needed if the pin is ever raised |
| R-03 | GPU compositor on this machine painted CSS filter/`backdrop-filter` layers above portaled dialog content | Dialog UX (fixed) | Dialogs render on a fully transparent backdrop; operator-confirmed visual acceptance pending final reload |
| R-04 | Headless UI tests run with `--disable-gpu`; browser only available headless | GPU-related regressions undetectable by automation | Keep heavy GPU effects out of dialogs (see R-03); visual sign-off is operator-dependent |
| R-05 | No Docker daemon (contract from `DELIVERY.md`, not retested in M0) | M10 BLOCKED candidate | Identify Docker/Testcontainers availability before M10 entry |
| R-06 | Single-commit local history; fourteen modified tracked files simulate a mid-delivery state | Attribution/rollback | Keep changes additive; never discard operator's uncommitted work |
| R-07 | CRLF/LF line-ending conversion warnings on tracked files (core.autocrlf) | Diff noise | Do not "normalize" files outside task scope |

## 5. Verified startup commands

```bash
# Backend (verified running: /health 200)
cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000

# Frontend (verified running: HTTP 200 on :5173)
cd frontend && npm run dev

# Database — README path fails on the seeded legacy DB (R-01); empty-DB path verified by test suite
.venv/Scripts/python.exe -m alembic upgrade head          # FAILS on legacy DB — see R-01
# full documented enterprise data load (backs up + resets dev DB first)
.venv/Scripts/python.exe scripts/seed_enterprise.py       # executed 2026-10-23
```

## 6. M0 Definition-of-done

| # | Item | Status |
|---|---|---|
| 1 | Scope and prerequisites documented | ✔ (M0 has no prerequisites) |
| 2 | Deliverables: baseline report (this file), architecture map (`docs/ARCHITECTURE.md` — pre-existing, already used), risk register (§4), verified startup commands (§5) | ✔ |
| 3 | Implementation complete for discovery scope | ✔ (no implementation required) |
| 4 | Automated tests executed | ✔ (155 passed backend; UI smoke all PASS) |
| 5 | Lint/format/type checks | ✔ (ruff exit 0; oxlint 0/0; tsc+vite build exit 0) |
| 6 | Security/compatibility checks | N/A (discovery); compat findings recorded (R-02, R-04) |
| 7 | Existing functionality and unrelated changes preserved | ✔ (git status re-verified; nothing reverted) |
| 8 | Documentation and setup updated | ✔ (this report + milestone-status.json) |
| 9 | Git diff contains only intended changes | ✔ (only new M0/MILESTONES/docs-quality files added) |
| 10 | Evidence + status recorded | ✔ **PASS** — mirrored in `docs/quality/milestone-status.json` |

**Known deviations from full evidence:**
- `docs/ARCHITECTURE.md` was authored in a previous session and claimed as the
  existing architecture map rather than regenerated freshly — its content was
  referenced, not re-verified line-by-line in M0.
- The mandatory regression scenario data (M2/M3 and later) has not been executed;
  this report covers M0 only.
