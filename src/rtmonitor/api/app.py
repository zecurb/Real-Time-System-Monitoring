"""FastAPI application factory for telemetry ingestion."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from rtmonitor.api.buffer import TelemetryBuffer
from rtmonitor.api.config import ApiSettings
from rtmonitor.api.contracts import AcceptedResponse, HealthResponse, TelemetryEventRequest
from rtmonitor.api.logging import configure_logging, log_event

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
    buffer: TelemetryBuffer | None = None,
) -> FastAPI:
    configure_logging()
    resolved_settings = settings or ApiSettings.from_environment()
    resolved_buffer = buffer or TelemetryBuffer(resolved_settings.buffer_capacity)
    app = FastAPI(
        title="Real-Time System Monitoring Ingestion API",
        version="0.2.0",
        description="Validates and buffers versioned telemetry events.",
    )
    app.state.settings = resolved_settings
    app.state.buffer = resolved_buffer

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
                "error": {
                    "code": "service_unavailable"
                    if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
                    else "http_error",
                    "message": str(exc.detail),
                },
                "request_id": request.state.request_id,
            },
        )

    @app.get("/health/live", response_model=HealthResponse)
    async def liveness() -> HealthResponse:
        return HealthResponse(
            status="ok",
            buffered_events=resolved_buffer.size(),
            buffer_capacity=resolved_buffer.capacity,
        )

    @app.get(
        "/health/ready",
        response_model=HealthResponse,
        responses={503: {"description": "The ingestion buffer is full."}},
    )
    async def readiness(response: Response) -> HealthResponse:
        if resolved_buffer.is_full():
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return HealthResponse(
                status="not_ready",
                buffered_events=resolved_buffer.size(),
                buffer_capacity=resolved_buffer.capacity,
            )
        return HealthResponse(
            status="ready",
            buffered_events=resolved_buffer.size(),
            buffer_capacity=resolved_buffer.capacity,
        )

    @app.post(
        "/v1/telemetry",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=AcceptedResponse,
        responses={
            413: {"description": "Request body is too large."},
            422: {"description": "Telemetry validation failed."},
            503: {"description": "The ingestion buffer is full."},
        },
    )
    async def ingest(event: TelemetryEventRequest, request: Request) -> AcceptedResponse:
        if not resolved_buffer.accept(event):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ingestion buffer is full",
                headers={"Retry-After": "5"},
            )
        log_event(
            LOGGER,
            "telemetry_accepted",
            {
                "request_id": request.state.request_id,
                "event_id": event.event_id,
                "node_id": event.node_id,
                "schema_version": event.schema_version,
                "buffered_events": resolved_buffer.size(),
            },
        )
        return AcceptedResponse(
            status="accepted",
            event_id=event.event_id,
            request_id=request.state.request_id,
            buffered_events=resolved_buffer.size(),
        )

    return app
