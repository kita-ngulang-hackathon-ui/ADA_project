FROM python:3.11-slim

# Install uv (single static binary, no extra package manager layer).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy the whole workspace: `uv sync --package worker` needs every workspace
# member's pyproject.toml to resolve local path dependencies (core-contracts,
# ingest-mapping, external-signals, graph-signal, churn-risk, impact,
# policy-guard, ranker, allocator, explain, measurement, feedback, persistence).
COPY pyproject.toml uv.lock* ./
COPY packages ./packages
COPY services ./services
COPY migrations ./migrations

# Deliberately WITHOUT the `tabpfn` extra. TabPFN pulls torch (multi-GB image)
# and downloads its weights on first use, which is exactly the venue-internet
# dependency section 4 says the demo must not have. churn-risk/impact/ranker
# each fall back to a deterministic scikit-learn stand-in when TabPFN is
# absent, so the pipeline runs identically offline, just under a different
# model name (SKLEARN_RANDOM_FOREST instead of TABPFN_CLASSIFIER).
# To demo real TabPFN: add `--extra tabpfn` here plus a weight-priming RUN,
# and expect a much larger image.
RUN uv sync --package worker --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}"

# TabPFN's own cache env, pointed at the tabpfn-cache volume so weights
# survive a container rebuild if the extra is ever enabled.
ENV TABPFN_MODEL_CACHE_DIR=/models

CMD ["python", "-m", "worker.main"]
