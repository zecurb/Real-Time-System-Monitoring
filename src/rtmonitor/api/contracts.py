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
