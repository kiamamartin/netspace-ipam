# NetSpace IPAM — task runner (platform-neutral: Windows Git Bash, Fedora/Linux)
# Quick reference: `make help`

.PHONY: help backend-setup backend-migrate run-backend run-frontend test lint verify docker-up docker-down

# Pick the Python launcher (first one that exists AND executes — skips the
# Microsoft Store 'python3' stub on Windows) and the venv interpreter, whichever
# venv layout exists (POSIX: .venv/bin/python; Windows: .venv/Scripts/python.exe).
# Paths are relative to backend/ so recipes can `cd backend` first.
PYTHON := $(shell for p in python3 python; do if command -v $$p >/dev/null 2>&1 && $$p -c 'pass' >/dev/null 2>&1; then echo $$p; break; fi; done)
BACKEND_PY := $(shell cd backend && ls .venv/bin/python .venv/Scripts/python.exe 2>/dev/null | head -n 1)

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-18s %s\n", $$1, $$2}'

# --- backend ---------------------------------------------------------------

backend-setup: ## Create the backend venv and install it (editable) with dev deps
	cd backend && $(PYTHON) -m venv .venv
	cd backend && .venv/bin/python -m pip install -e ".[dev]" 2>/dev/null \
		|| cd backend && .venv/Scripts/python -m pip install -e ".[dev]"

backend-migrate: ## Apply database migrations (Alembic) to the dev database
	cd backend && $(BACKEND_PY) -m alembic upgrade head

run-backend: ## Start the FastAPI backend on :8000
	cd backend && $(BACKEND_PY) -m uvicorn app.main:app --port 8000

run-frontend: ## Start the Vite dev server on :5173 (proxies /api to :8000)
	cd frontend && npm install --no-fund --no-audit && npm run dev

# --- checks ----------------------------------------------------------------

test: ## Run backend tests and the frontend production build (tsc + vite)
	cd backend && $(BACKEND_PY) -m pytest -q
	cd frontend && npm run build

lint: ## Lint both sides (ruff + oxlint)
	cd backend && $(BACKEND_PY) -m ruff check .
	cd frontend && npm run lint

verify: ## Full verification gates (deps, lockfile, lint, tests, secrets, health*; *needs uvicorn already running)
	bash scripts/verify-setup.sh

# --- docker (deployment parity check, e.g. on Fedora) ----------------------

docker-up: ## Build and start the Docker stack (web :8080, api :8000)
	docker compose up --build -d
	docker compose ps

docker-down: ## Stop the Docker stack and remove its test data volume
	docker compose down -v
