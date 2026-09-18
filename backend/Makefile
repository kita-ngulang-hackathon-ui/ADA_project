# Makefile for [PROJECT NAME TBD] backend. Run `make help`.
#
# Compose targets (up/down/migrate/...) are the local development loop.
# Production is a plain VM with no Docker: see deploy/DEPLOY.md and the
# deploy-* / run-* targets below.
SHELL := /bin/bash
.DEFAULT_GOAL := help
COMPOSE := docker compose
PY ?= python
API_BASE ?= http://localhost:8000
# Must be on CONSOLE_DEMO_REVIEWERS; there is no default reviewer (requirement 8).
REVIEWER ?= ops_reviewer_1

.PHONY: help up down logs migrate seed synthetic reseed pipeline demo test test-tabpfn test-invariants lint lint-imports typecheck fmt preflight clean deploy-sync deploy-migrate run-api run-worker check-llm

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

up: ## Start postgres, api, worker (local compose)
	@test -f .env || { echo "ERROR: .env missing. Run: cp .env.example .env"; exit 1; }
	$(COMPOSE) up -d --build

down: ## Stop all services
	$(COMPOSE) down

logs: ## Tail all logs
	$(COMPOSE) logs -f

migrate: ## Apply migrations and provision DB roles
	$(COMPOSE) run --rm migrate

synthetic: ## Regenerate synthetic fixtures (deterministic)
	uv run python -m tools.synthetic.generate

seed: ## Load tenants, mappings, incentives, canned feed, synthetic events
	uv run python -m tools.synthetic.load_fixture

reseed: ## Drop and reload demo data
	$(COMPOSE) down -v && $(MAKE) up migrate seed

pipeline: ## Trigger one full pipeline run per demo tenant
	@set -euo pipefail; \
	jar=$$(mktemp); trap 'rm -f $$jar' EXIT; \
	for slug in $$($(PY) -c "import json,pathlib; print(' '.join(json.loads(p.read_text(encoding='utf-8'))['tenant_slug'] for p in sorted(pathlib.Path('fixtures/mappings').glob('*.json'))))"); do \
	  curl -sf -c $$jar -X POST $(API_BASE)/console/v1/session \
	    -H 'Content-Type: application/json' \
	    -d "{\"tenant_slug\":\"$$slug\",\"reviewer_id\":\"$(REVIEWER)\"}" >/dev/null; \
	  echo "$$slug  $$(curl -sf -b $$jar -X POST $(API_BASE)/console/v1/pipeline/run)"; \
	done; \
	echo "Queued. The worker picks these up within WORKER_POLL_INTERVAL_SECONDS."

demo: up migrate seed ## Full bootstrap, then print demo URLs
	@echo "API docs        http://localhost:8000/docs"
	@echo "Health          http://localhost:8000/v1/health"
	@echo
	@echo "The console is a separate app. Start it from ../frontend (npm run dev),"
	@echo "with NEXT_PUBLIC_API_BASE_URL pointed at this API:"
	@echo "  Console         http://localhost:3000"
	@echo "  Client surface  http://localhost:3000/client-surface"
	@echo "  Measurement     http://localhost:3000/measurement"

test: ## Run the full Python test suite
	uv run pytest

test-tabpfn: ## Real TabPFN scorer + pipeline integration (needs TABPFN_TOKEN; slow on CPU)
	uv run pytest -m tabpfn services/worker/tests/test_real_tabpfn.py

test-invariants: ## Run the non-skippable invariant tests
	uv run pytest tests/invariants

lint: ## Ruff check
	uv run ruff check .

lint-imports: ## Enforce layer contracts (.importlinter)
	uv run lint-imports

typecheck: ## mypy over packages and services
	uv run mypy packages services

fmt: ## Format Python
	uv run ruff format .

check-llm: ## Smoke-test the configured EXPLAIN_LLM_* endpoint (e.g. local Qwen)
	uv run python deploy/check_llm.py

deploy-sync: ## Install the workspace into .venv on a VM (no Docker)
	uv sync --frozen --no-dev

deploy-migrate: ## Apply migrations and provision DB roles (needs MIGRATE_DATABASE_URL)
	uv run alembic -c migrations/alembic.ini upgrade head

# run-api / run-worker source .env themselves only to read API_HOST/API_PORT and
# WORKER_DATABASE_URL. Every other setting is loaded by pydantic-settings from
# .env at import time, which is why both must run with this directory as CWD.
run-api: ## Run the API in the foreground (systemd runs this via deploy/ada-api.service)
	@set -a; [ -f .env ] && . ./.env; set +a; \
	uv run uvicorn api.main:app --host "$${API_HOST:-0.0.0.0}" --port "$${API_PORT:-8000}"

run-worker: ## Run the worker in the foreground; DATABASE_URL must be the app_worker DSN
	@set -a; [ -f .env ] && . ./.env; set +a; \
	DATABASE_URL="$${WORKER_DATABASE_URL:?WORKER_DATABASE_URL is required}" uv run python -m worker.main


preflight: ## Offline readiness check before the venue (see DEMO_SCRIPT)
	@set -uo pipefail; \
	fail=0; \
	ok()   { echo "  ok    $$1"; }; \
	warn() { echo "  warn  $$1"; }; \
	bad()  { echo "  FAIL  $$1"; fail=1; }; \
	echo "Config"; \
	test -f .env && ok ".env present" || bad ".env missing (cp .env.example .env)"; \
	! grep -q '__TBD__' .env 2>/dev/null && ok "no __TBD__ left in .env" \
	  || warn "__TBD__ still in .env: $$(grep -c '__TBD__' .env) open decision(s)"; \
	echo "Images (must already be built; no pulls at the venue)"; \
	for svc in api worker; do \
	  $(COMPOSE) images -q $$svc 2>/dev/null | grep -q . && ok "$$svc image built" \
	    || bad "$$svc image missing (run: make up)"; \
	done; \
	echo "Offline demo data"; \
	ls fixtures/external/*.json >/dev/null 2>&1 && ok "canned external feed present" \
	  || bad "fixtures/external/*.json missing (demo would need live internet)"; \
	ls fixtures/mappings/*.json >/dev/null 2>&1 && ok "tenant mappings present" \
	  || bad "fixtures/mappings/*.json missing"; \
	! grep -q 'PROVISIONAL placeholder' fixtures/incentives.json 2>/dev/null \
	  && ok "incentive catalog is real" \
	  || warn "fixtures/incentives.json is still the placeholder catalog (open decision)"; \
	echo "Models"; \
	ok "TabPFN extra not installed; deterministic scikit-learn stand-in, no weight download"; \
	echo "Database"; \
	$(COMPOSE) exec -T postgres pg_isready >/dev/null 2>&1 && ok "postgres accepting connections" \
	  || warn "postgres not running (run: make up)"; \
	echo; \
	test $$fail -eq 0 && echo "PREFLIGHT PASS" || { echo "PREFLIGHT FAIL"; exit 1; }

clean: ## Remove containers, volumes, caches
	$(COMPOSE) down -v --remove-orphans
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
