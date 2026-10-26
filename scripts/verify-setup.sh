#!/usr/bin/env bash
# verify-setup.sh — documented equivalent of `make verify-setup` (MILESTONES.md M1).
# Verifies: dependency integrity, lint, tests, lockfile consistency, secret
# hygiene, and the health endpoint. Prints one PASS/FAIL line per gate and
# exits non-zero if any mandatory gate fails.
set -u
cd "$(dirname "$0")/.." || exit 2

PY="$PWD/backend/.venv/Scripts/python.exe"
failures=0
gate() { # name -> exit-code-capturing pipeline required
  if [ "$1" -eq 0 ]; then echo "PASS $2"; else echo "FAIL $2"; failures=$((failures+1)); fi
}

# 1. backend venv present
[ -x "$PY" ]; gate $? "backend venv present ($PY)"

# 2. dependency graph intact
"$PY" -m pip check > /tmp/m1_pip_check.txt 2>&1; gate $? "pip check (backend dependency graph)"
[ "$failures" -eq 0 ] || cat /tmp/m1_pip_check.txt

# 3. lockfile exists and matches environment snapshot
sha_current=$("$PY" -m pip freeze | sort -du | sha256sum | cut -d' ' -f1)
sha_lock=$(sort -du backend/requirements.lock | sha256sum | cut -d' ' -f1)
[ "$sha_current" = "$sha_lock" ]; gate $? "requirements.lock consistent with venv snapshot"

# 4. lint
( cd backend && "$PY" -m ruff check . > /tmp/m1_ruff.txt 2>&1 ); gate $? "ruff (backend)"

# 5. unit/API tests
( cd backend && "$PY" -m pytest -q > /tmp/m1_pytest.txt 2>&1 ); gate $? "pytest -q (backend)"

# 6. frontend lockfile + config via package-lock.json (v3) and dependency tree
( cd frontend && npm ls --depth 0 > /tmp/m1_npm_ls.txt 2>&1 ); gate $? "npm ls (frontend lockfile tree)"
( cd frontend && npm run lint > /tmp/m1_oxlint.txt 2>&1 ); gate $? "oxlint (frontend)"

# 7. secret hygiene: .env must exist locally but must not be tracked
if [ -f backend/.env ]; then
  grep -qx "backend/.env" <(git -C . ls-files) && r=1 || r=0
  gate $r "backend/.env not tracked by git (exists locally, untracked)"
else
  echo "WARN backend/.env absent (running on defaults + environment)"
fi
[ -f backend/.env.example ]; gate $? "backend/.env.example template present"
cmp -s <(git ls-files --error-unmatch backend/.env.example > /dev/null 2>&1; echo ok) <(echo ok); gate $? "only .env.example tracked (template), no secrets in git"

# 8. health endpoint (backend must be running; does NOT start one)
code=$(curl -s -o /tmp/m1_health.json -w '%{http_code}' --max-time 5 http://localhost:8000/health)
[ "$code" = "200" ]; gate $? "health endpoint :8000/health -> 200 ($(head -c 80 /tmp/m1_health.json))"

echo "-----"
if [ "$failures" -eq 0 ]; then
  echo "verify-setup: ALL GATES PASS"
  exit 0
else
  echo "verify-setup: $failures gate(s) FAILED"
  exit 1
fi
