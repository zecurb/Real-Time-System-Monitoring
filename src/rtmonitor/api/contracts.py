"""Strict API contracts for versioned telemetry events."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

Percentage = Annotated[float, Field(ge=0, le=100)]
NonNegativeInt = Annotated[int, Field(ge=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MemoryMetricsRequest(StrictModel):
    total_bytes: NonNegativeInt
    available_bytes: NonNegativeInt
    used_percent: Percentage


class DiskMetricsRequest(StrictModel):
    path: Annotated[str, Field(min_length=1, max_length=512)]
    total_bytes: NonNegativeInt
    free_bytes: NonNegativeInt
    used_percent: Percentage


class NetworkMetricsRequest(StrictModel):
    received_bytes: NonNegativeInt
    transmitted_bytes: NonNegativeInt


class SystemMetricsRequest(StrictModel):
    load_1m: NonNegativeFloat
    load_5m: NonNegativeFloat
    load_15m: NonNegativeFloat
    cpu_count: Annotated[int, Field(ge=1, le=65_536)]
    uptime_seconds: NonNegativeFloat
    process_count: NonNegativeInt
    memory: MemoryMetricsRequest
    disk: DiskMetricsRequest
    network: NetworkMetricsRequest


class TelemetryEventRequest(StrictModel):
    schema_version: Literal["1.0"]
    event_id: UUID
    node_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")]
    observed_at: datetime
    metrics: SystemMetricsRequest

    @field_validator("observed_at")
    @classmethod
    def observed_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value


class AcceptedResponse(StrictModel):
    status: Literal["accepted", "duplicate"]
    event_id: UUID
    request_id: str
    stored_events: NonNegativeInt
    queue_depth: NonNegativeInt


class HealthResponse(StrictModel):
    status: Literal["ok", "ready", "not_ready"]
    storage: Literal["unchecked", "available", "unavailable"]


class PipelineStatusResponse(StrictModel):
    pending: NonNegativeInt
    processing: NonNegativeInt
    retry: NonNegativeInt
    processed: NonNegativeInt
    dead_letter: NonNegativeInt
    active_depth: NonNegativeInt


class MetricPointResponse(StrictModel):
    event_id: UUID
    observed_at: datetime
    value: float
    labels: dict[str, str]


class MetricHistoryResponse(StrictModel):
    node_id: str
    metric_name: str
    start: datetime
    end: datetime
    points: list[MetricPointResponse]
    next_cursor: str | None


class NodeSummaryResponse(StrictModel):
    node_id: str
    last_seen: datetime
    event_count: NonNegativeInt


class NodeListResponse(StrictModel):
    nodes: list[NodeSummaryResponse]


class MetricDefinitionResponse(StrictModel):
    name: str
    display_name: str
    unit: str
    category: str


class MetricCatalogResponse(StrictModel):
    metrics: list[MetricDefinitionResponse]


class AnomalyResponse(StrictModel):
    event_id: UUID
    node_id: str
    metric_name: str
    observed_at: datetime
    value: float
    baseline: float
    dispersion: NonNegativeFloat
    score: NonNegativeFloat
    severity: Literal["warning", "critical"]
    sample_count: NonNegativeInt


class AnomalyListResponse(StrictModel):
    anomalies: list[AnomalyResponse]


class ForecastResponse(StrictModel):
    event_id: UUID
    node_id: str
    metric_name: str
    observed_at: datetime
    current_value: float
    threshold: float
    slope_per_hour: float
    hours_to_threshold: NonNegativeFloat
    predicted_at: datetime
    r_squared: Percentage
    confidence: Literal["medium", "high"]
    risk: Literal["watch", "warning", "critical"]
    sample_count: NonNegativeInt
    backtest_error: NonNegativeFloat | None
    provider: Literal["cpu", "gpu"]
    fallback_reason: str | None


class ForecastListResponse(StrictModel):
    forecasts: list[ForecastResponse]


class RuntimeResponse(StrictModel):
    requested: Literal["auto", "cpu", "gpu"]
    active: Literal["cpu", "gpu"]
    accelerator: str | None
    fallback_reason: str | None


class IncidentResponse(StrictModel):
    incident_id: UUID
    node_id: str
    metric_name: str
    status: Literal["open", "acknowledged", "resolved"]
    severity: Literal["warning", "critical"]
    title: str
    summary: str
    occurrence_count: NonNegativeInt
    first_seen: datetime
    last_seen: datetime
    owner: str | None
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    resolution_note: str | None
    revision: NonNegativeInt
    updated_at: datetime


class IncidentListResponse(StrictModel):
    incidents: list[IncidentResponse]


class IncidentTimelineEventResponse(StrictModel):
    timeline_id: UUID
    incident_id: UUID
    action: Literal["opened", "escalated", "acknowledged", "resolved", "reopened"]
    actor: str
    note: str | None
    from_status: Literal["open", "acknowledged", "resolved"] | None
    to_status: Literal["open", "acknowledged", "resolved"]
    occurred_at: datetime


class IncidentTimelineResponse(StrictModel):
    events: list[IncidentTimelineEventResponse]


Actor = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._@ -]{0,127}$",
    ),
]


class AcknowledgeIncidentRequest(StrictModel):
    actor: Actor
    note: Annotated[str | None, Field(max_length=2048)] = None
    expected_revision: NonNegativeInt


class ResolveIncidentRequest(StrictModel):
    actor: Actor
    note: Annotated[str, Field(min_length=3, max_length=2048)]
    expected_revision: NonNegativeInt
