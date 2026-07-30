"""FastAPI application factory for durable telemetry ingestion."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Path, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from rtmonitor.api.config import ApiSettings
from rtmonitor.api.contracts import (
    AcceptedResponse,
    AnomalyListResponse,
    AnomalyResponse,
    ForecastListResponse,
    ForecastResponse,
    HealthResponse,
    MetricCatalogResponse,
    MetricDefinitionResponse,
    MetricHistoryResponse,
    MetricPointResponse,
    NodeListResponse,
    NodeSummaryResponse,
    PipelineStatusResponse,
    RuntimeResponse,
    TelemetryEventRequest,
)
from rtmonitor.api.logging import configure_logging, log_event
from rtmonitor.api.pagination import decode_metric_cursor, encode_metric_cursor
from rtmonitor.execution import resolve_execution_provider
from rtmonitor.metrics import METRIC_DEFINITIONS
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
        version="0.8.0",
        description=(
            "Ingests telemetry and serves explainable anomalies and "
            "hardware-aware resource forecasts."
        ),
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

    @app.get("/v1/nodes", response_model=NodeListResponse)
    async def nodes(
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    ) -> NodeListResponse:
        discovered = await resolved_store.list_nodes(limit=limit)
        return NodeListResponse(
            nodes=[
                NodeSummaryResponse(
                    node_id=node.node_id,
                    last_seen=node.last_seen,
                    event_count=node.event_count,
                )
                for node in discovered
            ]
        )

    @app.get("/v1/metrics", response_model=MetricCatalogResponse)
    async def metric_catalog() -> MetricCatalogResponse:
        return MetricCatalogResponse(
            metrics=[
                MetricDefinitionResponse(
                    name=definition.name,
                    display_name=definition.display_name,
                    unit=definition.unit,
                    category=definition.category,
                )
                for definition in METRIC_DEFINITIONS
            ]
        )

    @app.get("/v1/anomalies", response_model=AnomalyListResponse)
    async def anomalies(
        start: Annotated[datetime, Query()],
        end: Annotated[datetime, Query()],
        node_id: Annotated[str | None, Query(min_length=3, max_length=128)] = None,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    ) -> AnomalyListResponse:
        if (
            start.tzinfo is None
            or start.utcoffset() is None
            or end.tzinfo is None
            or end.utcoffset() is None
        ):
            raise HTTPException(status_code=400, detail="start and end must include timezones")
        if start >= end:
            raise HTTPException(status_code=400, detail="start must be before end")
        if end - start > timedelta(days=31):
            raise HTTPException(status_code=400, detail="query range cannot exceed 31 days")
        findings = await resolved_store.list_anomalies(
            node_id=node_id,
            start=start,
            end=end,
            limit=limit,
        )
        return AnomalyListResponse(
            anomalies=[
                AnomalyResponse(
                    event_id=uuid.UUID(finding.event_id),
                    node_id=finding.node_id,
                    metric_name=finding.metric_name,
                    observed_at=finding.observed_at,
                    value=finding.value,
                    baseline=finding.baseline,
                    dispersion=finding.dispersion,
                    score=finding.score,
                    severity=finding.severity,
                    sample_count=finding.sample_count,
                )
                for finding in findings
            ]
        )

    @app.get("/v1/runtime", response_model=RuntimeResponse)
    async def runtime() -> RuntimeResponse:
        provider = resolve_execution_provider()
        return RuntimeResponse(
            requested=provider.requested,
            active=provider.active,
            accelerator=provider.accelerator,
            fallback_reason=provider.fallback_reason,
        )

    @app.get("/v1/forecasts", response_model=ForecastListResponse)
    async def forecasts(
        node_id: Annotated[str | None, Query(min_length=3, max_length=128)] = None,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    ) -> ForecastListResponse:
        results = await resolved_store.list_forecasts(node_id=node_id, limit=limit)
        return ForecastListResponse(
            forecasts=[
                ForecastResponse(
                    event_id=uuid.UUID(item.event_id),
                    node_id=item.node_id,
                    metric_name=item.metric_name,
                    observed_at=item.observed_at,
                    current_value=item.current_value,
                    threshold=item.threshold,
                    slope_per_hour=item.slope_per_hour,
                    hours_to_threshold=item.hours_to_threshold,
                    predicted_at=item.predicted_at,
                    r_squared=item.r_squared * 100,
                    confidence=item.confidence,
                    risk=item.risk,
                    sample_count=item.sample_count,
                    backtest_error=item.backtest_error,
                    provider=item.provider,
                    fallback_reason=item.fallback_reason,
                )
                for item in results
            ]
        )

    @app.get(
        "/v1/metrics/{node_id}",
        response_model=MetricHistoryResponse,
        responses={400: {"description": "Invalid time range or cursor."}},
    )
    async def metric_history(
        node_id: Annotated[
            str,
            Path(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$"),
        ],
        metric: Annotated[str, Query(min_length=1, max_length=128)],
        start: Annotated[datetime, Query()],
        end: Annotated[datetime, Query()],
        limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
        cursor: Annotated[str | None, Query(max_length=512)] = None,
    ) -> MetricHistoryResponse:
        if (
            start.tzinfo is None
            or start.utcoffset() is None
            or end.tzinfo is None
            or end.utcoffset() is None
        ):
            raise HTTPException(status_code=400, detail="start and end must include timezones")
        if start >= end:
            raise HTTPException(status_code=400, detail="start must be before end")
        if end - start > timedelta(days=31):
            raise HTTPException(status_code=400, detail="query range cannot exceed 31 days")
        try:
            decoded_cursor = decode_metric_cursor(cursor) if cursor else None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid metric cursor") from exc

        samples = await resolved_store.query_metric_samples(
            node_id=node_id,
            metric_name=metric,
            start=start,
            end=end,
            limit=limit + 1,
            cursor=decoded_cursor,
        )
        has_more = len(samples) > limit
        page = samples[:limit]
        next_cursor = encode_metric_cursor(page[-1]) if has_more and page else None
        return MetricHistoryResponse(
            node_id=node_id,
            metric_name=metric,
            start=start,
            end=end,
            points=[
                MetricPointResponse(
                    event_id=uuid.UUID(sample.event_id),
                    observed_at=sample.observed_at,
                    value=sample.value,
                    labels=sample.labels,
                )
                for sample in page
            ],
            next_cursor=next_cursor,
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
