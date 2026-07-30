"""FastAPI application factory for durable telemetry ingestion."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from rtmonitor.api.config import ApiSettings
from rtmonitor.api.contracts import (
    AcceptedResponse,
    HealthResponse,
    PipelineStatusResponse,
    TelemetryEventRequest,
)
from rtmonitor.api.logging import configure_logging, log_event
from rtmonitor.storage import EventStore, SqlAlchemyEventStore, StoreResult
from rtmonitor.storage.sqlalchemy import StorageUnavailableError

LOGGER = logging.getLogger("rtmonitor.api")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _request_id(request: Request) -> str:
    supplied = request.headers.get("X-Request-ID", "")
    if REQUEST_ID_PATTERN.fullmatch(supplied):
        return supplied
    return str(uuid.uuid4())


def create_app(
    *,
    settings: ApiSettings | None = None,
    store: EventStore | None = None,
) -> FastAPI:
    configure_logging()
    resolved_settings = settings or ApiSettings.from_environment()
    resolved_store = store or SqlAlchemyEventStore(resolved_settings.database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        await resolved_store.close()

    app = FastAPI(
        title="Real-Time System Monitoring Ingestion API",
        version="0.4.0",
        description="Validates, stores, and queues versioned telemetry events.",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def request_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = _request_id(request)
        request.state.request_id = request_id
        started_at = time.perf_counter()
        response: Response

        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                request_size = int(content_length)
            except ValueError:
                request_size = resolved_settings.max_request_bytes + 1
            if request_size > resolved_settings.max_request_bytes:
                response = JSONResponse(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    content={
                        "error": {
                            "code": "payload_too_large",
                            "message": "request body exceeds the configured limit",
                        },
                        "request_id": request_id,
                    },
                )
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)

        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 3)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = str(elapsed_ms)
        log_event(
            LOGGER,
            "http_request",
            {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": elapsed_ms,
            },
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "telemetry event failed validation",
                    "details": jsonable_encoder(exc.errors()),
                },
                "request_id": request.state.request_id,
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "error": {"code": "http_error", "message": str(exc.detail)},
                "request_id": request.state.request_id,
            },
        )

    @app.get("/health/live", response_model=HealthResponse)
    async def liveness() -> HealthResponse:
        return HealthResponse(status="ok", storage="unchecked")

    @app.get("/health/ready", response_model=HealthResponse)
    async def readiness(response: Response) -> HealthResponse:
        if not await resolved_store.ping():
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return HealthResponse(status="not_ready", storage="unavailable")
        return HealthResponse(status="ready", storage="available")

    @app.get("/v1/pipeline/status", response_model=PipelineStatusResponse)
    async def pipeline_status() -> PipelineStatusResponse:
        stats = await resolved_store.queue_stats()
        return PipelineStatusResponse(
            pending=stats.pending,
            processing=stats.processing,
            retry=stats.retry,
            processed=stats.processed,
            dead_letter=stats.dead_letter,
            active_depth=stats.pending + stats.processing + stats.retry,
        )

    @app.post(
        "/v1/telemetry",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=AcceptedResponse,
        responses={
            413: {"description": "Request body is too large."},
            422: {"description": "Telemetry validation failed."},
            503: {"description": "Durable storage is unavailable."},
        },
    )
    async def ingest(event: TelemetryEventRequest, request: Request) -> AcceptedResponse:
        try:
            result = await resolved_store.store(event)
            stored_events = await resolved_store.count()
            queue_depth = await resolved_store.queue_depth()
        except StorageUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="durable telemetry storage is unavailable",
                headers={"Retry-After": "5"},
            ) from exc

        response_status: Literal["accepted", "duplicate"]
        response_status = "duplicate" if result is StoreResult.DUPLICATE else "accepted"
        log_event(
            LOGGER,
            "telemetry_stored",
            {
                "request_id": request.state.request_id,
                "event_id": event.event_id,
                "node_id": event.node_id,
                "schema_version": event.schema_version,
                "result": result,
                "stored_events": stored_events,
                "queue_depth": queue_depth,
            },
        )
        return AcceptedResponse(
            status=response_status,
            event_id=event.event_id,
            request_id=request.state.request_id,
            stored_events=stored_events,
            queue_depth=queue_depth,
        )

    return app
