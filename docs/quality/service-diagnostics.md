# Service diagnostics — M10 (M10-AC-006)

Date: 2026-11-05 · Roadmap: `MILESTONES.md` §M10 · Stack: `docker-compose.yml`
(backend python:3.12-slim + uvicorn, frontend nginx:1.27-alpine)

All commands below were executed and verified against the running deployment
(2026-11-05). Substitute the documented ports when the stack uses a port
override (e.g. `NETSPACE_API_PORT=18000` when host 8000 is occupied).

## Health

```sh
curl -fsS http://127.0.0.1:8000/health
# {"status":"ok","app":"NetSpace IPAM","version":"1.0.0","database":"sqlite",
#  "algorithm_version":"vlsm-1.0.0"}
./scripts/healthcheck.sh            # API + read model + web UI, exit 0/1
docker compose ps                   # backend should show "(healthy)"
```

Notes: `/health` is process liveness + identity, not a database probe; an
unreachable database shows as `500` with the standard error envelope on data
endpoints (see `docs/quality/recovery.md` §1).

## Container state

```sh
docker compose ps -a                # exited containers keep a name + exit code
docker inspect netspace-ipam-backend-1 --format '{{.State.Status}} {{.State.ExitCode}}'
```

Exit 137 on stop = the 10-second SIGTERM grace elapsed (normal during drills);
a crash-loop shows as repeated `Restarting`/`Exited` here.

## Logs

```sh
docker compose logs backend         # app life cycle + request access lines
docker compose logs frontend        # nginx entrypoint + access logs
docker compose logs -f backend      # follow
```

Backend logging is configured by `app/core/logging.py` (`NETSPACE_LOG_LEVEL`):
ISO-8601 timestamps, level, logger name — e.g.
`2026-11-05T10:32:04+0000 INFO [netspace] Starting NetSpace IPAM (DB: sqlite)`.
Alembic migration progress is interleaved in the same stream at startup.

## Storage

```sh
docker volume ls | grep netspace    # named volume netspace-ipam_netspace-data
docker exec netspace-ipam-backend-1 ls -la /data
```

The SQLite database lives at `/data/netspace.db` inside the named volume —
rebuilding the images never destroys stored data; `docker compose down -v`
does (explicitly destructive).

## Common failure modes and first actions

| Symptom | First action |
| --- | --- |
| `docker compose up` exits: host port already bound | change the host mapping via a compose override file or stop the conflicting service |
| backend `Exited` immediately after start | `docker compose logs backend` — check migration output and `NETSPACE_DATABASE_URL` |
| `/health` 200 but data endpoints 500 | database unreachable — check the volume/URL (`docker exec ... ls /data`, see recovery doc) |
| web 200 but API errors | backend healthy? `./scripts/healthcheck.sh` isolates which leg fails |
| container stops during drill scripts | drill scripts re-locate and restart the backend automatically; check `docker compose ps -a` |

## Verified evidence record

- `curl /health` → 200 JSON `status:ok` (behind `NETSPACE_API_PORT=18000` override)
- `./scripts/healthcheck.sh` → 3 PASS, exit 0
- `docker compose ps` → backend `Up (healthy)`, frontend `Up`
- `docker compose logs backend` → migration lines, uvicorn startup,
  structured app logging, request access lines
- `./scripts/backup-restore-drill.sh` → PASS (see
  `docs/baseline/m10-deployment-operations.md`)
