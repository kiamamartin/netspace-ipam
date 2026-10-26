# M1 Gate Evidence — Architecture and Engineering Foundation

Date: 2026-10-23 · Recorded per `MILESTONES.md` §2-M1. Status after evidence: **PASS**.

## Criteria → evidence

| Criterion | Evidence (executed 2026-10-23) |
|---|---|
| Clean setup succeeds via documented commands | Fresh throwaway venv created from `backend/requirements.lock` (all 42 pins); `import app.main` → `fresh-venv import app.main OK`, exit 0; temp venv removed afterwards. Frontend `npm ls --depth 0` resolves the tree against `package-lock.json` v3 |
| No secrets committed to source control | Pattern scan of `backend/app` (api_key/apikey/secret/password/passwd/token assignments) → 0 matches; `backend/.env` exists locally and is NOT tracked by git; only the `backend/.env.example` template is tracked. Scan values were never echoed |
| Lockfiles present and consistent | `frontend/package-lock.json` (v3) + `npm ls` clean; NEW `backend/requirements.lock` (42 pins) — script verifies sha256 of sorted `pip freeze` matches the lock |
| Health endpoint responds correctly when executed | `GET http://localhost:8000/health` → 200 with body `{"status":"ok","app":"NetSpace IPAM","version":"1.0.0","database":"sqlite","algorithm_version":"vlsm-1.0.0"}` |
| Backend and frontend boundaries documented | `docs/ARCHITECTURE.md` (pre-existing, referenced by M0) documents `app/api/` routes per resource, service/design layers, and the thin-client frontend rule |
| Configuration loaded from environment, not hardcoded | `backend/app/core/config.py`: pydantic `Settings` with `NETSPACE_*` env prefix, `.env` support, only safe development defaults; `backend/.env.example` template exists |

## Gate command

`make verify-setup` does not exist in this repository. Documented equivalent, kept under
version control and used as the M1 gate command:

```bash
bash scripts/verify-setup.sh   # 11 gates; final line "verify-setup: ALL GATES PASS", exit 0
```

Gates exercised (all PASS, exit 0): backend venv present · `pip check` clean ·
`requirements.lock` sha consistent with venv snapshot · `ruff` clean · `pytest -q`
155 passed · frontend `npm ls` clean · `oxlint` 0/0 · `.env` untracked with template
tracked · health endpoint 200.

First script run exposed a genuine path bug (relative `$PY` broken inside the
`cd backend` subshell) that produced false ruff/pytest FAILs; fixed to an absolute
path and re-run — both then PASS with the same lofted evidence. No test or
assertion was weakened.

## Dependency-graph repair during M1

`pip check` initially reported `sqlalchemy 2.0.55 requires greenlet, which is not
installed` — a fallout of the M0-era `pip install --force-reinstall --no-deps`
swap that worked around the OS Application Control block of SQLAlchemy 2.1.4's
compiled DLLs (R-02). greenlet is declared by SQLAlchemy itself on win32, so
installing it restored the *existing declared* dependency graph rather than
adding a new one. After the repair: `pip check` → `No broken requirements found.`,
exit 0. The fixture `requirements.lock` snapshot includes it.

## Deliverables

- Architecture document — `docs/ARCHITECTURE.md` (pre-existing, verified referenced)
- Environment templates — `backend/.env.example` (backend)
- Dependency lockfiles — `frontend/package-lock.json` (existing) + `backend/requirements.lock` (new, full-environment snapshot)
- Health endpoint — `/health` verified live
- Gate script — `scripts/verify-setup.sh` (new, documented `make verify-setup` equivalent)

## Universal definition-of-done

| # | Item | Status |
|---|---|---|
| 1 | Scope and prerequisites documented | ✔ (M0 PASS recorded) |
| 2 | Deliverables exist and reviewed | ✔ (see list above) |
| 3 | Implementation complete for M1 scope | ✔ (no new runtime behavior required; repo already satisfies each criterion) |
| 4 | Automated tests actually executed | ✔ (pytest 155 passed; oxlint; npm ls; smoke suite still green from same-session run) |
| 5 | Linting/formatting/type checks pass | ✔ (ruff exit 0, oxlint 0 warnings/0 errors, `npm run build` exit 0) |
| 6 | Security/compatibility checks pass | ✔ (secret scan 0 matches; .env untracked; OWASP-style auth checks belong to M5, not M1) |
| 7 | Existing functionality and unrelated changes preserved | ✔ (git status re-checked: only M0/M1 additive files added; the operator's pre-existing modified and untracked files remain untouched) |
| 8 | Documentation and setup updated | ✔ (this report + `scripts/verify-setup.sh` self-documenting + milestone-status.json) |
| 9 | Git diff contains only intended changes | ✔ (new: `MILESTONES.md`, `scripts/verify-setup.sh`, `backend/requirements.lock`, `docs/baseline/`, `docs/quality/`) |
| 10 | Evidence and status recorded | ✔ **PASS** — mirrored in `docs/quality/milestone-status.json` |

## Known deviations

- MILESTONES.md was received truncated at §3 (M11-AC-007 cites "§7", which is not in
  the file yet). M1 criteria were fully specified in §2, so the gate is unaffected;
  the missing sections are awaited from the operator.
- `make verify-setup` itself cannot run — the repository has no Make tool target;
  the script above is the documented equivalent authorized by §2-M1 ("or documented
  equivalent").
