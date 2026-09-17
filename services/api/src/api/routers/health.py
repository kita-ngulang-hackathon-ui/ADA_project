"""GET /v1/health -- liveness, no auth, no tenant data."""
from datetime import UTC, datetime

from fastapi import APIRouter

router = APIRouter(tags=["health"])

_VERSION = "0.2.0"


@router.get("/v1/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": _VERSION,
        "time": datetime.now(UTC).isoformat(),
    }
