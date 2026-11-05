# NetSpace IPAM — Runbooks

Operational procedures for the deployed stack (`docker-compose.yml`: backend
uvicorn + frontend nginx). Task automation lives in the `Makefile`; gate
scripts live in `scripts/`. The command-by-command diagnostic reference is
[service-diagnostics.md](quality/service-diagnostics.md); recovery specifics
(backup format, restore drill, migration drills) are
[recovery.md](quality/recovery.md).

All addresses below assume the compose defaults (API `:8000`, web `:8080`).
When host `8000` is taken, deploy with the documented port override
(`NETSPACE_API_PORT`/`NETSPACE_WEB_PORT`, e.g. `18000`/`18080` used during the
M10 gate run) and substitute everywhere.

## 1. Start / stop / restart

```sh
docker compose up -d --build      # build + start (web waits on backend health)
docker compose ps                 # backend should be Up (healthy)
docker compose down               # stop; keep volume
docker compose down -v            # stop AND drop the data volume (destructive)
docker compose restart backend    # bounce one service
```

## 2. Routine health check

```sh
curl -fsS http://127.0.0.1:8000/health    # {"status":"ok",...}
./scripts/healthcheck.sh                  # API + read model + web UI; exit 0 = all PASS
docker compose logs backend --tail 100    # look for tracebacks
```

`/health` is process liveness + identity, not a database probe: an unreachable
database keeps `/health` at `200` and shows up as `500`-with-error-envelope on
data endpoints until the DB recovers (the backend reconnects without a
restart; verified in `docs/quality/recovery.md` §1).

## 3. Backup drill

```sh
./scripts/backup-restore-drill.sh
```

Runs a consistent backup of the **running** database (SQLite `VACUUM INTO` is
an atomic snapshot — no service pause needed), checks integrity, and stores it
under `backups/` as `netspace-YYYYMMDD-HHMMSS-backup.db`, then hashes it
and host-side to prove the copy matches. The backup leg is safe to run
against a live stack; it leaves state untouched.

Do not hand-roll ad-hoc `sqlite3` backups of a live database — the drill is
the verified path (consistency + integrity + sha256 both sides).

## 4. Restore drill (taken down / disaster)

The second half of `./scripts/backup-restore-drill.sh` demonstrates a
taken-down restore end to end:

1. writes a throwaway drill marker row (proof the current DB is NOT the
   backup point),
2. stops the backend (`docker compose stop backend`),
3. copies the verified snapshot into the `/data` named volume using a one-shot
   helper container on the backend image (needed because `docker cp` cannot
   write into a stopped container's volume mount), hash-verifies what landed
   in the volume,
4. starts the backend again and verifies: `/health` 200, row counts equal the
   pre-drill snapshot, the marker row is gone, and the API read model answers.

The same helper-container copy is the technique for restoring a snapshot to a
fresh volume by hand. `backend/tests/test_migrations.py` pins the Alembic
`upgrade head`/`downgrade base` behavior; M10 executed this drill live
(`docs/baseline/m10-deployment-operations.md`).

## 5. Database migrations

```sh
cd backend && .venv/bin/python -m alembic upgrade head      # local dev DB
docker compose up -d --build                                # in containers: runs on startup
```

Known risk R-01: a *legacy* seeded SQLite file from before Alembic (no
`alembic_version` table) fails `upgrade head` with
`table departments already exists`. Production evidence covers empty/isolated
databases. Remediating such a database is an operator data-migration task —
do not point a legacy file at a new schema blindly.

## 6. Upgrades and rollback

1. Read `DELIVERY.md` §Milestone status and confirm gates are PASS on the
   commit you deploy.
2. Take a snapshot (`scripts/backup-restore-drill.sh` backup leg).
3. `docker compose up -d --build`.
4. `./scripts/healthcheck.sh` plus a login + dashboard spot check.
5. Rollback = stop, restore the pre-upgrade snapshot, start the previous
   image tag (images built by compose are kept locally; re-tag before
   rebuilding if you need an exact rollback anchor).

## 7. Anything broken / first responder

| Symptom | First actions |
| --- | --- |
| `/health` not 200 | `docker compose ps`, `docker compose logs backend --tail 200`; expect a crash-loop to show as `Restarting`. Restart with `docker compose restart backend` |
| Data endpoints `500` | Database unreachable/recovering — backend keeps serving `/health` 200 and reconnects; see recovery.md §1 |
| Login always `401` | Account deactivated or wrong seed password; admin-only reset via another admin or re-seed (DATA.md) |
| Login `429` | Rate limit (5/60 s per IP); wait one minute |
| Web up, API down | Backend container health; frontend proxies act as bearer of the outage, check `docker compose logs frontend` |
| `docker compose` can't reach daemon | See R-05 in `docs/quality/milestone-status.json`: use the systemd daemon (`DOCKER_HOST=unix:///var/run/docker.sock`); a stale `desktop-linux` CLI context is a known false alarm |

## 8. Release verification (M11 gate)

```sh
make release-check          # backend pytest + ruff, frontend tsc+vite build + oxlint
# accessibility + 27-check smoke need a live stack:
#   backend on :8001, vite dev on :5173, then:
cd frontend && SMOKE_USER=... SMOKE_PASS=... EDGE_PATH=<chromium-path> npm run test:ui
cd frontend && SMOKE_USER=... SMOKE_PASS=... EDGE_PATH=<chromium-path> npm run test:a11y
```

Expected: `223 passed`, ruff All checks passed, vite build clean, oxlint one
pre-existing advisory in `src/ui.tsx`, `A11Y PASSED` (7 pages), smoke 27 PASS.
Gate evidence for the current release: `docs/baseline/m11-release-certification.md`.
