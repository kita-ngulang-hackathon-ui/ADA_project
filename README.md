# [PROJECT NAME TBD]

Retention and loyalty recommendation engine for Indonesian fintechs.
Built for Hackathon UI 2026 (Universitas Indonesia, 17–18 Sep 2026), BNI Ventures
challenge track: customer retention and transaction loyalty.

Team: Aidam, Randuichi Touya, Abdurrahman Ammar Abqary.

The two halves are hosted separately and are developed independently.

| Folder | What it is | Docs |
| --- | --- | --- |
| [`backend/`](backend/) | Python: the FastAPI ingestion + console API, the pipeline worker, 13 domain packages, Alembic migrations, demo fixtures. Self-contained — nothing in it refers outside the folder. | [`backend/README.md`](backend/README.md), [`backend/deploy/DEPLOY.md`](backend/deploy/DEPLOY.md) |
| [`frontend/`](frontend/) | Next.js 15 console and simulated client surface. | [`frontend/README.md`](frontend/README.md) |

## How they connect

The frontend talks only to the backend's `/console/v1` surface over HTTP. There
is no shared code, no shared build and no database access from the frontend.

Two settings have to agree, one on each side:

- `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` — the backend's origin.
- `API_CORS_ORIGINS` in `backend/.env` — must list the frontend's origin.

Each folder has its own `.env.example`; there is no shared environment file.

All demo data is **synthetic**.
