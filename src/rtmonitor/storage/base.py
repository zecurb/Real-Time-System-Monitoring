"""Storage contracts independent of a database implementation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol

from rtmonitor.api.contracts import TelemetryEventRequest


class StoreResult(StrEnum):
    CREATED = "created"
    DUPLICATE = "duplicate"


class QueueStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    RETRY = "retry"
    PROCESSED = "processed"
    DEAD_LETTER = "dead_letter"


@dataclass(frozen=True, slots=True)
class QueueLease:
    event_id: str
    payload: dict[str, object]
    attempt: int


@dataclass(frozen=True, slots=True)
class QueueStats:
    pending: int = 0
    processing: int = 0
    retry: int = 0
    processed: int = 0
    dead_letter: int = 0


@dataclass(frozen=True, slots=True)
class MetricSample:
    event_id: str
    node_id: str
    metric_name: str
    observed_at: datetime
    value: float
    labels: dict[str, str]


@dataclass(frozen=True, slots=True)
class NodeSummary:
    node_id: str
    last_seen: datetime
    event_count: int


@dataclass(frozen=True, slots=True)
class Anomaly:
    event_id: str
    node_id: str
    metric_name: str
    observed_at: datetime
    value: float
    baseline: float
    dispersion: float
    score: float
    severity: Literal["warning", "critical"]
    sample_count: int


@dataclass(frozen=True, slots=True)
class Forecast:
    event_id: str
    node_id: str
    metric_name: str
    observed_at: datetime
    current_value: float
    threshold: float
    slope_per_hour: float
    hours_to_threshold: float
    predicted_at: datetime
    r_squared: float
    confidence: Literal["medium", "high"]
    risk: Literal["watch", "warning", "critical"]
    sample_count: int
    backtest_error: float | None
    provider: Literal["cpu", "gpu"]
    fallback_reason: str | None


class EventStore(Protocol):
    async def store(self, event: TelemetryEventRequest) -> StoreResult: ...

    async def count(self) -> int: ...

    async def queue_depth(self) -> int: ...

    async def queue_stats(self) -> QueueStats: ...

    async def query_metric_samples(
        self,
        *,
        node_id: str,
        metric_name: str,
        start: datetime,
        end: datetime,
        limit: int,
        cursor: tuple[datetime, str] | None = None,
    ) -> list[MetricSample]: ...

    async def query_recent_metric_samples(
        self,
        *,
        node_id: str,
        metric_name: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[MetricSample]: ...

    async def list_nodes(self, *, limit: int) -> list[NodeSummary]: ...

    async def list_anomalies(
        self,
        *,
        node_id: str | None,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[Anomaly]: ...

    async def list_forecasts(
        self, *, node_id: str | None, limit: int
    ) -> list[Forecast]: ...

    async def ping(self) -> bool: ...

    async def close(self) -> None: ...
