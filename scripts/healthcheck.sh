#!/usr/bin/env bash
# NetSpace IPAM — deployment health check (M10-AC-002).
#
# Usage: ./scripts/healthcheck.sh
# Environment:
#   NETSPACE_API_PORT  host port of the API container   (default 8000)
#   NETSPACE_WEB_PORT  host port of the web container   (default 8080)
#   NETSPACE_API_HOST  host or address for the API      (default 127.0.0.1)
#   NETSPACE_WEB_HOST  host or address for the web      (default 127.0.0.1)
set -euo pipefail

API_HOST="${NETSPACE_API_HOST:-127.0.0.1}"
API_PORT="${NETSPACE_API_PORT:-8000}"
WEB_HOST="${NETSPACE_WEB_HOST:-127.0.0.1}"
WEB_PORT="${NETSPACE_WEB_PORT:-8080}"
failures=0

# 1. API health endpoint
health_body="$(curl -fsS -m 5 "http://${API_HOST}:${API_PORT}/health" 2>/dev/null)" || {
  echo "FAIL api health endpoint unreachable at http://${API_HOST}:${API_PORT}/health"
  failures=$((failures + 1))
  health_body=""
}
if [ -n "$health_body" ]; then
  if printf '%s' "$health_body" | grep -q '"status":"ok"'; then
    echo "PASS api /health -> 200 status=ok"
  else
    echo "FAIL api /health did not report status=ok: ${health_body}"
    failures=$((failures + 1))
  fi
fi

# 2. API inventory read model (answers with data even for the empty database)
if curl -fsS -m 5 "http://${API_HOST}:${API_PORT}/api/v1/networks" >/dev/null 2>&1; then
  echo "PASS api /api/v1/networks -> 200"
else
  echo "FAIL api /api/v1/networks not reachable"
  failures=$((failures + 1))
fi

# 3. Web UI answers
if curl -fsS -m 5 -o /dev/null "http://${WEB_HOST}:${WEB_PORT}/"; then
  echo "PASS web ui -> 200"
else
  echo "FAIL web ui not reachable at http://${WEB_HOST}:${WEB_PORT}/"
  failures=$((failures + 1))
fi

if [ "$failures" -gt 0 ]; then
  echo "HEALTHCHECK FAILED (${failures} failing check(s))"
  exit 1
fi
echo "HEALTHCHECK PASSED"
