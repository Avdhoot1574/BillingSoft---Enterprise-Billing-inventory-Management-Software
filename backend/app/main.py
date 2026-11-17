import logging
import re
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.db.session import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
_REQUEST_ID_OK = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Business Billing Platform API", version="0.1.0",
                    debug = True,
                  docs_url="/docs" if settings.app_env != "production" else None,
                  redoc_url=None, openapi_url="/openapi.json" if settings.app_env != "production" else None)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Company-Id", "X-Request-ID", "Idempotency-Key"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        incoming = request.headers.get("x-request-id", "")
        request.state.request_id = incoming if _REQUEST_ID_OK.match(incoming) else uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    register_error_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", tags=["ops"])
    def health():
        return {"status": "ok"}

    @app.get("/ready", tags=["ops"])
    def ready():
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}

    return app


app = create_app()
