import json
import logging
import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException

from app.config import settings
from app.db import engine
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.domain import router as domain_router
from app.routers.imports import router as imports_router
from app.routers.ingestion import router as ingestion_router
from app.routers.jobs import router as jobs_router
from app.routers.outcomes import router as outcomes_router
from app.routers.persistence import router as persistence_router
from app.routers.reconcile import router as reconcile_router
from app.routers.records import router as records_router
from app.routers.signing import router as signing_router
from app.services.access import request_id_context

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
logger = logging.getLogger("mineassure")

app = FastAPI(title="MineAssure API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

PREFIX = settings.api_prefix
app.include_router(auth_router, prefix=PREFIX)
app.include_router(reconcile_router, prefix=PREFIX)
app.include_router(persistence_router, prefix=PREFIX)
app.include_router(domain_router, prefix=PREFIX)
app.include_router(imports_router, prefix=PREFIX)
app.include_router(admin_router, prefix=PREFIX)
app.include_router(jobs_router, prefix=PREFIX)
app.include_router(records_router, prefix=PREFIX)
app.include_router(ingestion_router, prefix=PREFIX)
app.include_router(outcomes_router, prefix=PREFIX)
app.include_router(signing_router, prefix=PREFIX)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    context_token = request_id_context.set(request.state.request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_context.reset(context_token)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; frame-ancestors 'none'"
    )
    response.headers["Cache-Control"] = "no-store"
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains"
        )
    return response


_rate_buckets: dict[str, deque] = defaultdict(deque)
_RATE_LIMIT = 300
_RATE_WINDOW = 60

_metrics: dict[str, int] = defaultdict(int)


@app.middleware("http")
async def request_size_limit(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 2 * 1024 * 1024:
        return JSONResponse(
            status_code=413,
            content={
                "detail": "Request body too large",
                "error": {"code": "413", "message": "Request body too large"},
            },
        )
    return await call_next(request)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if settings.environment in ("test", "development"):
        return await call_next(request)
    client = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = _rate_buckets[client]
    while bucket and bucket[0] < now - _RATE_WINDOW:
        bucket.popleft()
    if len(bucket) >= _RATE_LIMIT:
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded",
                "error": {"code": "429", "message": "Rate limit exceeded"},
            },
        )
    bucket.append(now)
    return await call_next(request)


@app.middleware("http")
async def structured_logging(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    _metrics[f"{request.method} {response.status_code}"] += 1
    logger.info(
        json.dumps(
            {
                "request_id": getattr(request.state, "request_id", None),
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            }
        )
    )
    return response


@app.get("/metrics")
def metrics():
    return {"counts": dict(_metrics)}


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error": {
                "code": str(exc.status_code),
                "message": exc.detail,
                "request_id": getattr(request.state, "request_id", None),
            },
        },
    )


@app.exception_handler(IntegrityError)
async def conflict_error(request, exc):
    return JSONResponse(
        status_code=409,
        content={
            "detail": "Conflicting or duplicate record",
            "error": {
                "code": "conflict",
                "message": "Conflicting or duplicate record",
                "request_id": getattr(request.state, "request_id", None),
            },
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Do not echo credentials or imported source values in the error envelope.
    errors = [
        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            {
                "detail": errors,
                "error": {
                    "code": "validation",
                    "message": "Request validation failed",
                    "request_id": getattr(request.state, "request_id", None),
                },
            }
        ),
    )


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}


@app.get("/ready")
def ready():
    try:
        with engine.connect() as c:
            c.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {"status": "ready"}
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
