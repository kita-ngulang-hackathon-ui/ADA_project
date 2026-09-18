# Deploying the backend to a VM

This is the production path: a plain Linux VM running Postgres, the API and the
worker as systemd services, with no Docker. The `docker-compose.yml` at the
backend root is for local development only.

Everything the backend needs is inside this `backend/` folder. Nothing outside
it is referenced, so you can upload the folder on its own.

## What runs

| Process | Command | Unit |
| --- | --- | --- |
| API | `uvicorn api.main:app` on port 8000 | `ada-api.service` |
| Worker | `python -m worker.main` | `ada-worker.service` |
| Postgres 16 | system package | `postgresql.service` |

The worker is a poll loop: it claims rows from `pipeline_runs` with
`FOR UPDATE SKIP LOCKED` and runs the pipeline per tenant. It takes no inbound
traffic and needs no port.

## Prerequisites

- Linux with systemd
- Python 3.11 or newer
- PostgreSQL 16
- [`uv`](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`

## 1. Upload

Put the folder at `/opt/ada/backend` (any path works; if you change it, change
the paths in both `.service` files to match).

```sh
# From your machine, from the repository root:
rsync -av --exclude '.venv' --exclude '__pycache__' --exclude '.env' \
      backend/ ada@YOUR_HOST:/opt/ada/backend/
```

Or clone the repository on the host and work inside `backend/`.

Create the service account that will own the files and run both units:

```sh
sudo useradd --system --home /opt/ada --shell /usr/sbin/nologin ada
sudo chown -R ada:ada /opt/ada
```

## 2. Provision Postgres

Create the database and a superuser role for migrations. The application roles
(`app_console`, `app_worker`, `app_readonly`) are **not** created here —
migration `0001_tenants_and_roles.py` creates them, using the passwords you put
in `.env`.

```sh
sudo -u postgres createdb retention
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'pick-a-strong-one';"
```

If Postgres runs on another host, make sure the VM can reach it and that
`pg_hba.conf` accepts the connection.

## 3. Configure

```sh
cd /opt/ada/backend
cp .env.example .env
chmod 600 .env
$EDITOR .env
```

Values you must change from the example:

- **`POSTGRES_HOST`** — the example says `postgres`, which is the compose
  service name. On a VM this is `localhost` (or your database host).
- **All five DSNs** (`DATABASE_URL`, `WORKER_DATABASE_URL`,
  `READONLY_DATABASE_URL`, `MIGRATE_DATABASE_URL`) and the three
  `APP_*_DB_PASSWORD` values. The passwords in the DSNs must match the
  `APP_*_DB_PASSWORD` values — migration 0001 sets the roles' passwords from
  the latter, and the services connect with the former.
- **The four secrets** — `PSEUDONYM_HMAC_SECRET`, `MEASUREMENT_HMAC_SECRET`,
  `CONSOLE_SESSION_SECRET`, `API_KEY_HASH_PEPPER`. Generate each with
  `openssl rand -hex 32`. Rotating `PSEUDONYM_HMAC_SECRET` after ingestion has
  started orphans every existing pseudonym, so set it once.
- **`API_CORS_ORIGINS`** — the deployed console's exact origin, including
  scheme and port (`https://console.example.com`). Get this wrong and the
  browser blocks every `/console/v1` call.
- **Every `__TBD__`** — these are deliberate open decisions. The application
  refuses to start rather than inventing a value, and `bootstrap.sh` refuses to
  run while any remain.

Then the worker's database override:

```sh
cp deploy/worker.env.example deploy/worker.env
chmod 600 deploy/worker.env
$EDITOR deploy/worker.env    # set DATABASE_URL to the app_worker DSN
```

This one file is easy to skip and expensive to skip. Both the API and the
worker read `DATABASE_URL`, but they must connect as *different* roles: the API
as `app_console`, the worker as `app_worker`. `docker-compose.yml` does this
override for the container path; on a VM, `deploy/worker.env` is what does it.
Without it the worker runs as `app_console`, which defeats the row-level
security installed by migration `0006_rls.py` and the approval separation that
`tests/invariants/test_worker_role_cannot_approve.py` exists to guard.

## 4. Install and migrate

```sh
cd /opt/ada/backend
sudo -u ada ./deploy/bootstrap.sh
```

This runs `uv sync --frozen --no-dev` (creating `.venv/`) and then
`alembic -c migrations/alembic.ini upgrade head`. It is idempotent — re-run it
after every deploy.

Both steps need this directory as the working directory: `alembic.ini` sets
`script_location = migrations` and `prepend_sys_path = .`, both relative paths.

### Size the VM for torch

`services/worker/pyproject.toml` lists `tabpfn==9.0.0` as a hard dependency,
which pulls torch. Expect several GB of download and disk on the first
`uv sync`, and give the VM headroom accordingly.

This is deliberate for a VM deploy, not an oversight. `.env.example` ships
`CHURN_SCORER_ENABLED=true`, and `worker/churn_scorer.py` imports
`TabPFNClassifier` directly and exits with status 1 if the trained scorer
cannot load. The container build skips the TabPFN *extra* (see the comment in
`services/worker/Dockerfile`), which only affects the models in `churn-risk`,
`impact` and `ranker` — those each fall back to a deterministic scikit-learn
stand-in. The trained scorer in `artifacts/` is separate and always needs
torch.

If you want a light VM without the trained scorer, set
`CHURN_SCORER_ENABLED=false` and drop `tabpfn` from the worker's dependencies.
The pipeline then runs entirely on the scikit-learn stand-ins, under a
different model name in the audit trail (`SKLEARN_RANDOM_FOREST` rather than
`TABPFN_ARTIFACT_*`).

## 5. Optional: connect the narrator to a local Qwen3

The pipeline's only generative step is the recommendation narration. It speaks
plain OpenAI `/chat/completions`, so a Qwen3-8B served on the same VM works
with configuration alone — no code change.

After running the bundle's `./setup.sh`:

```sh
cd qwen3-8b-backend-bundle
grep '^API_KEY=' .env          # the generated key
```

Then in `/opt/ada/backend/.env`:

```ini
EXPLAIN_LLM_ENABLED=true
EXPLAIN_LLM_BASE_URL=http://127.0.0.1:8000/v1
EXPLAIN_LLM_MODEL=qwen3-8b
EXPLAIN_LLM_API_KEY=<the key from above>
EXPLAIN_LLM_EXTRA_BODY={"chat_template_kwargs":{"enable_thinking":false}}
EXPLAIN_LLM_TIMEOUT_S=60
```

Verify it before restarting the worker:

```sh
cd /opt/ada/backend && make check-llm
```

Three things to get right:

1. **Port collision.** The bundle serves on 8000, which is also this API's
   default port. Move one of them: set `API_PORT=8001` in `.env` and the
   matching `--port` in `deploy/ada-api.service`, or serve Qwen elsewhere and
   change `EXPLAIN_LLM_BASE_URL`.
2. **`enable_thinking` must be false.** Qwen3 otherwise opens a
   `<think>` block and spends the whole 220-token budget reasoning, leaving no
   narration. The narrator strips any block that still arrives, but a reply
   that is *only* a scratchpad is treated as a failure.
3. **Raise `EXPLAIN_LLM_TIMEOUT_S`.** The default of 6 seconds targets a hosted
   API. An 8B model on CPU needs far longer; a timeout is not an error, it
   silently falls back to the template.

Narration is never trusted. `explain.validate_narration` rejects any number or
identifier that is not in the fact sheet, and every rejection, timeout or
connection failure falls back to the deterministic template. The stored
`reason_source` records which one was used (`LLM` or `TEMPLATE`), so if the
console shows `TEMPLATE` everywhere after wiring this up, check
`journalctl -u ada-worker` for `narration fell back to template`.

Leaving `EXPLAIN_LLM_ENABLED=false` is a valid deploy; the pipeline produces
template narrations and nothing else changes.

## 6. Start the services

```sh
sudo cp deploy/ada-api.service deploy/ada-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ada-api ada-worker
```

Check them:

```sh
systemctl status ada-api ada-worker
curl -sf http://localhost:8000/v1/health
journalctl -u ada-worker -f          # should show the poll loop, no path errors
```

## 7. Seed and smoke-test

Load the demo tenants, mappings, incentives and canned feed:

```sh
cd /opt/ada/backend && sudo -u ada make seed
```

> `tools/synthetic/generate.py` and `load_fixture.py` are currently
> unimplemented stubs, so `make seed` and `make synthetic` fail today. Until
> they are written, seed the database by another route.

Then trigger one pipeline run per tenant and watch the worker pick it up:

```sh
make pipeline
journalctl -u ada-worker -n 50
```

## Updating

```sh
cd /opt/ada/backend
git pull                              # or re-rsync
sudo -u ada ./deploy/bootstrap.sh
sudo systemctl restart ada-api ada-worker
```

## Pointing the console at this backend

The console in `../frontend` is built and hosted separately. Set its
`NEXT_PUBLIC_API_BASE_URL` to this host's public origin, and add that console's
origin to `API_CORS_ORIGINS` here. Session cookies are sent cross-origin, so
both sides must be HTTPS in production.

## Troubleshooting

**`Cannot build a migration connection string; missing [...]`** — `migrations/env.py`
reads the process environment directly and never loads `.env` itself.
`bootstrap.sh` sources `.env` before calling alembic; if you run alembic by
hand, export `MIGRATE_DATABASE_URL` first.

**The worker starts, then exits on a missing artifact** — almost always a
working-directory problem. `worker/settings.py` resolves
`fixtures/external`, `artifacts` and `fixtures/churn_scorer_mapping.json`
relative to the CWD. Confirm `WorkingDirectory=` in the unit points at the
folder that contains `fixtures/` and `artifacts/`.

**Empty configuration / required-field errors at startup** — same cause. Both
settings classes load `env_file=".env"` relative to the CWD.

**`permission denied for table ...` in the worker log** — `deploy/worker.env`
is missing, unreadable, or still has the placeholder DSN, so the worker
connected as the wrong role.

**Every narration says `TEMPLATE` after wiring up the LLM** — run
`make check-llm`. In the worker log, `narration fell back to template
(ConnectError)` means the endpoint is unreachable, `(ReadTimeout)` means
`EXPLAIN_LLM_TIMEOUT_S` is too low for a local model, `(HTTPStatusError)` means
a bad API key or model name, and `(NarrationRejected)` means the model invented
a number — expected occasionally, and the correct behaviour.
