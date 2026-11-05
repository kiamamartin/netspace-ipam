# M10 — Deployment and Operations

> **Authority:** `MILESTONES.md` §M10. This file is the executed evidence
> record for the M10 gate, executed 2026-11-05 against a live Docker daemon.

## Scope

Docker-based deployment, production configuration, migrations, health checks,
logs, backups, restoration.

## Deliverables (all exist and were executed)

- Reproducible deployment — `docker-compose.yml` + `backend/Dockerfile`
  (python:3.12-slim) + `frontend/Dockerfile` (node:22-alpine → nginx:1.27)
- Operator guide — `docs/quality/service-diagnostics.md` (verified commands),
  `docs/quality/recovery.md` (backup/restore procedure)
- Backup/restore scripts — `scripts/healthcheck.sh`,
  `scripts/backup-restore-drill.sh` (both written for this gate and run)
- Service diagnostics — see diagnostics doc; symptom/first-action table

## Acceptance criteria evidence

### M10-AC-001 Fresh deployment succeeds from a clean environment

- Images built from scratch this session (no cached project images):
  `netspace-ipam-backend:latest` and `netspace-ipam-frontend:latest`
  ("CreatedSince: 18–19 minutes" at gate time).
- `docker compose up -d --build` → backend became `healthy`, frontend `Up`
  (compose web UI `depends_on: service_healthy` gated startup).
- Documented instructions: README + Makefile (`make docker-up` /
  `scripts/healthcheck.sh`). Port override note: host 8000 was occupied by an
  unrelated operator container, so this deployment ran with a compose port
  override (`18000:8000`, `18080:80`); the default mapping (8000/8080) is
  unchanged for clean environments.

### M10-AC-002 Health checks functional

- Compose-level healthcheck (`urllib` probe on `/health`) → backend
  `Up (healthy)`.
- `./scripts/healthcheck.sh` (run with `NETSPACE_API_PORT=18000
  NETSPACE_WEB_PORT=18080`):
  `PASS api /health -> 200 status=ok · PASS api /api/v1/networks -> 200 ·
  PASS web ui -> 200 · HEALTHCHECK PASSED` (exit 0).

### M10-AC-003 Logging configured and verified

- `docker compose logs backend`: Alembic migration sequence (0001→0002→0003),
  uvicorn startup log, structured application log line
  (`2026-11-05T10:32:04+0000 INFO [netspace] Starting NetSpace IPAM (DB:
  sqlite)`), and 86 request/access INFO lines accumulated during the drill.
- `docker compose logs frontend`: nginx entrypoint + access logs.
- Log level configurable via `NETSPACE_LOG_LEVEL`.

### M10-AC-004 Backup procedure executed successfully

- `./scripts/backup-restore-drill.sh` produced
  `backups/netspace-20261105-134949-backup.db` via SQLite `VACUUM INTO`
  (atomic, consistent snapshot), integrity check `ok`.
- Artifact hash verified on both sides:
  `sha256 aa47276d78784a0a78792aa4ea9615adb45b21e22e118c85d566c3fcd647ad6f`
  (container == host).

### M10-AC-005 Restore drill executed successfully (demonstrated)

- Demonstrated as a taken-down drill, not merely documented:
  1. pre-drill row counts 12 networks / 42 subnets / 3 users;
  2. post-backup mutation inserted a marker row (networks 12→13);
  3. backend stopped; backup woven into the shared named volume by a helper
     container (docker cp cannot write a stopped container's volume mount);
  4. restored file hash matched the artifact; backend restarted;
     `/health` and the read model answered;
  5. post-restore counts == 12/42/3 and the marker was rolled back.
- Script exit 0: `BACKUP/RESTORE DRILL PASSED`.

### M10-AC-006 Service diagnostics documented and verified

- `docs/quality/service-diagnostics.md`: health, container state, logs,
  storage, failure-mode table — every command in the doc was executed against
  the running deployment (2026-11-05).

## Notes

- R-05 (Docker daemon unavailable) is resolved: Docker is installed with an
  active systemd daemon (`/var/run/docker.sock`); only the Docker Desktop
  socket path referenced by the CLI context was absent, which is bypassed via
  `DOCKER_HOST=unix:///var/run/docker.sock`.
- `netspace.db` deployment seeder: the fresh container database had no
  accounts; the enterprise seed was executed inside the container to supply a
  realistic dataset for the drill (12 networks / 42 subnets / 3 role accounts
  — the DELIVERY seeded-dataset numbers).
