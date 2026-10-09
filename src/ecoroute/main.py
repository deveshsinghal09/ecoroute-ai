import json
import logging
import time
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from ecoroute.auth import CognitoVerifier
from ecoroute.config import Settings
from ecoroute.routers import ROUTERS
from ecoroute.storage import Conflict, DynamoStore, LocalStore, Unavailable
from ecoroute.environment.api import router as environmental_router
from ecoroute.routing.api import router as routing_router
from ecoroute.routing.models import RoutingError
from ecoroute.ml.api import router as ml_router
from ecoroute.ml.inference import MLUnavailable
from ecoroute.wearable.api import router as wearable_router
from ecoroute.advisory.api import router as advisory_router

logger = logging.getLogger("ecoroute")
logger.setLevel(logging.INFO)


def error(request, status, code, headers=None):
    return JSONResponse({"error": {"code": code, "request_id": getattr(request.state, "request_id", "")}},
                        status_code=status, headers=headers)


def create_app(settings: Settings | None = None, *, store=None, verifier=None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="EcoRoute AI", version="0.1.0", docs_url="/docs", redoc_url=None,
                  description="Backend, environmental datasets and provider-backed route comparison. Trained ML is not connected.")
    app.state.settings = settings
    app.state.verifier = verifier or CognitoVerifier(settings)
    if store is None and settings.ecoroute_profile == "aws":
        client = boto3.client("dynamodb", region_name=settings.aws_region,
                             config=Config(connect_timeout=2, read_timeout=3,
                                           retries={"max_attempts": 2, "mode": "standard"}))
        store = DynamoStore(client, {
            "journeys": settings.journeys_table, "telemetry": settings.journeys_table,
            "preferences": settings.preferences_table, "routes": settings.route_metadata_table, "route_cache": settings.route_metadata_table,
            "alerts": settings.alerts_table,
            "notification_state": settings.alerts_table, "workflows": settings.alerts_table,
            "schools": settings.preferences_table, "notification_config": settings.preferences_table,
        }, settings.idempotency_table)
    app.state.store = store if store is not None else LocalStore(settings.local_db_path)
    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                           allow_methods=["GET", "POST", "PUT", "DELETE"],
                           allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
                           allow_credentials=False)

    @app.middleware("http")
    async def observability(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        started = time.monotonic()
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 262144:
                return error(request, 413, "request_too_large")
        request._body = bytes(body)
        try:
            response = await call_next(request)
        except Exception:
            response = error(request, 500, "internal_error")
        route = request.scope.get("route")
        logger.info(json.dumps({"event": "http_request", "request_id": request.state.request_id,
                                "route": getattr(route, "path", "unmatched"),
                                "status": response.status_code,
                                "latency_ms": round((time.monotonic() - started) * 1000, 2)}))
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error(request, exc.status_code, exc.detail, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error(request, 422, "validation_error")

    @app.exception_handler(RoutingError)
    async def routing_error(request, exc):
        return error(request, exc.status, exc.code)

    @app.exception_handler(MLUnavailable)
    async def ml_unavailable(request, exc):
        return error(request, 503, str(exc))

    @app.exception_handler(Conflict)
    async def conflict_error(request, exc):
        return error(request, 409, "idempotency_conflict")

    async def dependency_error(request, exc):
        return error(request, 503, "storage_unavailable")
    for exception in (BotoCoreError, ClientError, Unavailable):
        app.add_exception_handler(exception, dependency_error)

    @app.get("/healthz", include_in_schema=False)
    @app.get("/api/v1/health", tags=["operations"])
    def health():
        return {"status": "ok", "profile": settings.ecoroute_profile, "phase": "1-foundation",
                "live_domain_providers": False}

    @app.get("/api/v1/ready", tags=["operations"])
    def ready():
        try:
            available = app.state.store.ready() and app.state.verifier.configured
        except Exception:
            available = False
        return JSONResponse({"status": "ready" if available else "not_ready"},
                            status_code=200 if available else 503)

    for router in ROUTERS:
        app.include_router(router, prefix="/api/v1")
    app.include_router(environmental_router, prefix="/api/v1")
    app.include_router(routing_router, prefix="/api/v1")
    app.include_router(ml_router, prefix="/api/v1")
    app.include_router(wearable_router, prefix="/api/v1")
    app.include_router(advisory_router, prefix="/api/v1")
    return app


app = create_app()
