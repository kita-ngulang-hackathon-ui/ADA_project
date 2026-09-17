"""FastAPI app factory (see services/api/README.md).

TODO:
- create_app(): include health, ingest, and console routers.
- Register error handlers from errors.py and request-id middleware.
- CORS from settings.API_CORS_ORIGINS.
"""


def create_app():
    raise NotImplementedError


# app = create_app()  # TODO: enable once implemented (uvicorn api.main:app)
