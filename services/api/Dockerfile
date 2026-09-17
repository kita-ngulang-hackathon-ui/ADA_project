FROM python:3.11-slim

# Install uv (single static binary, no extra package manager layer).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy the whole workspace: `uv sync --package api` needs every workspace
# member's pyproject.toml to resolve local path dependencies
# (core-contracts, ingest-mapping, measurement, persistence).
COPY pyproject.toml uv.lock* ./
COPY packages ./packages
COPY services ./services
COPY migrations ./migrations

RUN uv sync --package api --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}"
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
