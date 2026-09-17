"""FastAPI app factory (see services/api/README.md).

Mounts the ingestion surface (`/v1`) and the console surface
(`/console/v1`). Registers the error envelope handlers and a request-id
middleware so every error response carries a `request_id` for correlation.
This module -- and nothing that imports from it -- ever imports
churn_risk/impact/ranker/allocator/explain or the worker; `.importlinter`'s
`api-no-scoring` contract makes that a build break, not a review comment.
"""
from __future__ import annotations

import asyncio
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.errors import ApiError, api_error_handler, internal, unhandled_exception_handler
from api.routers import health, ingest
from api.routers.console import (
    allocations,
    audit,
    external_signals,
    feedback,
    incentives,
    mappings,
    measurement,
    pipeline,
    recommendations,
    tenants,
    users,
)
from api.routers.console import (
    session as console_session,
)
from api.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="[PROJECT NAME TBD] API", version="0.2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_and_timeout(request: Request, call_next):
        request.state.request_id = f"req_{uuid.uuid4().hex[:20]}"
        start = time.monotonic()
        try:
            response = await asyncio.wait_for(
                call_next(request), timeout=settings.api_request_timeout_seconds
            )
        except TimeoutError:
            return await api_error_handler(
                request, internal(f"request exceeded API_REQUEST_TIMEOUT_SECONDS={settings.api_request_timeout_seconds}s")
            )
        except ApiError as exc:
            return await api_error_handler(request, exc)
        except Exception as exc:  # noqa: BLE001 -- last-resort envelope, not a silent 500
            return await unhandled_exception_handler(request, exc)
        response.headers["X-Request-Id"] = request.state.request_id
        elapsed = time.monotonic() - start
        response.headers["X-Response-Time-Ms"] = f"{elapsed * 1000:.1f}"
        return response

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(health.router)
    app.include_router(ingest.router)

    app.include_router(console_session.router)
    app.include_router(tenants.router)
    app.include_router(mappings.router)
    app.include_router(incentives.router)
    app.include_router(external_signals.router)
    app.include_router(users.router)
    app.include_router(pipeline.router)
    app.include_router(allocations.router)
    app.include_router(recommendations.router)
    app.include_router(measurement.router)
    app.include_router(feedback.router)
    app.include_router(audit.router)

    return app


app = create_app()
