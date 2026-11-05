#!/usr/bin/env bash
# NetSpace IPAM — backup and restore DRILL (M10-AC-004, M10-AC-005).
#
# Demonstrates, end to end:
#   1. a consistent backup of the running database (SQLite VACUUM INTO)
#   2. a verified artifact hash on both the container side and the host
#   3. a TAKEN-DOWN restore: backend stopped, backup woven back into the
#      shared volume, restarted — post-mutation marker data proves that the
#      stack rolled back to the backup point.
#
# Usage: ./scripts/backup-restore-drill.sh
# Environment:
#   NETSPACE_BACKEND_CONTAINER  container name override        (default: via docker compose ps)
#   NETSPACE_API_PORT           health port after restoration  (default 8000, override when mapped)
set -euo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"

BACKEND_DEV="/data/netspace.db"
API_PORT="${NETSPACE_API_PORT:-8000}"
stamp="$(date +%Y%m%d-%H%M%S)"
out_dir="backups"
mkdir -p "$out_dir"
artifact="${out_dir}/netspace-${stamp}-backup.db"

log() { echo "[drill] $*"; }
die() { echo "[drill] FATAL: $*" >&2; exit 1; }

# --- locate the backend container -------------------------------------------
if [ -n "${NETSPACE_BACKEND_CONTAINER:-}" ]; then
  container="$NETSPACE_BACKEND_CONTAINER"
else
  container="$(docker compose -f docker-compose.yml ps -a -q backend | head -n1)"
fi
[ -n "$container" ] || die "backend container not found (docker compose not in the expected state)"

state="$(docker inspect "$container" --format '{{.State.Status}}')"
if [ "$state" != "running" ]; then
  log "backend is ${state}; starting it for the preflight..."
  docker compose -f docker-compose.yml start backend
  for i in $(seq 1 30); do
    state="$(docker inspect "$container" --format '{{.State.Status}}')"
    curl -fsS -m 2 "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1 || sleep 1
    [ "$state" = "running" ] && break
    [ "$i" = 30 ] && die "backend could not be started (state: ${state})"
  done
fi
log "target container: ${container}"

# --- 0. preflight -----------------------------------------------------------
docker exec "$container" sh -c "test -f ${BACKEND_DEV}" \
  || die "database file ${BACKEND_DEV} not found in ${container}"
counts_before="$(docker exec -i "$container" python3 - <<'PY'
import sqlite3
db = sqlite3.connect("file:/data/netspace.db?mode=ro", uri=True)
for table in ("networks", "subnets", "users"):
    print(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
PY
)" || die "cannot read row counts"
log "row counts before (networks/subnets/users): $(printf '%s/' $counts_before)"

# --- 1. consistent backup (VACUUM INTO = atomic snapshot) ------------------
docker exec -i "$container" python3 - <<'PY' || die "VACUUM INTO failed"
import sqlite3
c = sqlite3.connect("/data/netspace.db")
c.execute("VACUUM INTO '/data/dr-backup.db'")
c.close()
PY
docker exec "$container" test -f /data/dr-backup.db || die "backup snapshot was not created"
_hash="$(docker exec "$container" sha256sum /data/dr-backup.db | awk '{print $1}')"
integrity="$(docker exec "$container" python3 -c "import sqlite3; print(sqlite3.connect('file:/data/dr-backup.db?mode=ro', uri=True).execute('PRAGMA integrity_check').fetchone()[0])")"
[ "$integrity" = "ok" ] || die "backup integrity check failed: ${integrity}"
log "backup integrity: ok (sha256 ${_hash:0:12}...)"

docker cp "$container:/data/dr-backup.db" "$artifact"
host_hash="$(sha256sum "$artifact" | awk '{print $1}')"
[ "$host_hash" = "$_hash" ] || die "artifact hash mismatch (host ${host_hash} vs container ${_hash})"
log "artifact ${artifact} verified: sha256 ${host_hash}"
docker exec "$container" rm -f /data/dr-backup.db

# --- 2. post-backup mutation (drill marker) ---------------------------------
docker exec -i "$container" python3 - <<'PY' || die "cannot insert drill marker"
import sqlite3, datetime
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
c = sqlite3.connect("/data/netspace.db")
c.execute(
    "INSERT INTO networks (name, cidr, family, description, environment, status, created_at, updated_at)"
    " VALUES ('dr-restore-marker', '10.253.0.0/24', 4, NULL, 'production', 'active', ?, ?)",
    (now, now),
)
c.commit()
c.close()
PY
counts_after_marker="$(docker exec "$container" python3 -c "import sqlite3; print(sqlite3.connect('/data/netspace.db').execute('SELECT COUNT(*) FROM networks').fetchone()[0])")"
log "drill marker written (networks ${counts_after_marker})"

# --- 3. taken-down restore ---------------------------------------------------
# docker cp cannot write into a stopped container's volume mount, so the
# backup is woven into the shared named volume by a one-shot helper container
# using the backend's own image (no network pull).
log "stopping backend for the restore window..."
docker compose -f docker-compose.yml stop backend

volume="$(docker inspect "$container" --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}')"
[ -n "$volume" ] || { docker compose -f docker-compose.yml start backend; die "volume for /data not found on ${container}"; }
image="$(docker inspect "$container" --format '{{.Config.Image}}')"
artifact_abs="$(pwd)/$artifact"
docker run --rm -v "$volume":/data -v "$artifact_abs":/artifact/db:ro "$image" \
  python3 -c 'import shutil; shutil.copyfile("/artifact/db", "/data/netspace.db")' \
  || { docker compose -f docker-compose.yml start backend; die "restore copy failed"; }

restored_hash="$(docker run --rm -v "$volume":/data -v "$artifact_abs":/artifact/db:ro "$image" \
  sha256sum /data/netspace.db | awk '{print $1}')"
[ "$restored_hash" = "$host_hash" ] || die "restored file hash mismatch"
log "restored file verified: sha256 ${restored_hash}"

docker compose -f docker-compose.yml start backend
for i in $(seq 1 30); do
  curl -fsS -m 2 "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1 && break
  [ "$i" = 30 ] && die "backend did not become healthy after restore"
  sleep 1
done
log "backend healthy after restore"

# --- 4. verification: state == pre-drill state ------------------------------
counts_after_restore="$(docker exec -i "$container" python3 - <<'PY'
import sqlite3
db = sqlite3.connect("file:/data/netspace.db?mode=ro", uri=True)
for table in ("networks", "subnets", "users"):
    print(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
PY
)"
[ "$counts_after_restore" = "$counts_before" ] || die "row counts diverged: before=[$(printf '%s ' $counts_before)] after=[$(printf '%s ' $counts_after_restore)]"
marker="$(docker exec "$container" python3 -c "import sqlite3; print(sqlite3.connect('/data/netspace.db').execute(\"SELECT COUNT(*) FROM networks WHERE name='dr-restore-marker'\").fetchone()[0])")"
[ "$marker" = "0" ] || die "drill marker still present — restore did not roll back"
log "row counts match the backup point; marker rolled back"

curl -fsS -m 5 "http://127.0.0.1:${API_PORT}/api/v1/networks" >/dev/null || die "API read model unreachable after restore"

log "BACKUP/RESTORE DRILL PASSED (artifact: ${artifact})"
