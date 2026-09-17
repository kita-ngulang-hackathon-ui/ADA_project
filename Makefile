# Makefile for [PROJECT NAME TBD]. Run `make help`.
# TODO: fill in recipes as services become runnable.
SHELL := /bin/bash
.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help up down logs migrate seed synthetic reseed pipeline demo test test-invariants lint lint-imports typecheck fmt preflight clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

up: ## Start postgres, api, worker, web
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
	@echo "TODO: POST /console/v1/pipeline/run for each demo tenant"

demo: up migrate seed ## Full bootstrap, then print demo URLs
	@echo "Console         http://localhost:3000"
	@echo "Client surface  http://localhost:3000/client-surface"
	@echo "Measurement     http://localhost:3000/measurement"
	@echo "API docs        http://localhost:8000/docs"

test: ## Run the full Python test suite
	uv run pytest

test-invariants: ## Run the non-skippable invariant tests
	uv run pytest tests/invariants

lint: ## Ruff check
	uv run ruff check .

lint-imports: ## Enforce layer contracts (.importlinter)
	uv run lint-imports

typecheck: ## mypy + tsc
	uv run mypy packages services
	cd apps/web && pnpm typecheck

fmt: ## Format Python
	uv run ruff format .

preflight: ## Offline readiness check before the venue (see DEMO_SCRIPT)
	@echo "TODO: verify images cached, TabPFN weights present, canned feed present, fonts self-hosted"

clean: ## Remove containers, volumes, caches
	$(COMPOSE) down -v --remove-orphans
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
