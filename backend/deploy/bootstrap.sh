#!/usr/bin/env bash
# Install dependencies and bring the database schema up to date.
#
# Run from the backend directory on the target host:
#   ./deploy/bootstrap.sh
#
# Idempotent: safe to re-run after every deploy. See DEPLOY.md for the full
# runbook, including Postgres provisioning and the systemd units.
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is not installed. Install it with:" >&2
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo "ERROR: .env missing. Run: cp .env.example .env  (then fill it in)" >&2
  exit 1
fi

if grep -q '__TBD__' .env; then
  echo "ERROR: .env still contains __TBD__ placeholders:" >&2
  grep -n '__TBD__' .env >&2
  echo "These are deliberate open decisions; the app fails at startup rather" >&2
  echo "than inventing a value. Fill them in before deploying." >&2
  exit 1
fi

echo "==> Installing the workspace into .venv"
# The whole workspace, so one venv serves both the API and the worker.
uv sync --frozen --no-dev

echo "==> Applying migrations"
# alembic.ini sets script_location=migrations and prepend_sys_path=. , both
# relative to this directory, which is why we cd'd above. The migrations
# connect as a superuser via MIGRATE_DATABASE_URL (or the POSTGRES_* parts),
# because migration 0001 creates the app_console/app_worker/app_readonly roles.
set -a
# shellcheck disable=SC1091
. ./.env
set +a
uv run alembic -c migrations/alembic.ini upgrade head

echo
echo "Done. Next:"
echo "  sudo systemctl restart ada-api ada-worker"
echo "  curl -sf http://localhost:\${API_PORT:-8000}/v1/health"
