"""Versioned telemetry event models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class MemoryMetrics:
    total_bytes: int
    available_bytes: int
    used_percent: float


@dataclass(frozen=True, slots=True)
class DiskMetrics:
    path: str
    total_bytes: int
    free_bytes: int
    used_percent: float


@dataclass(frozen=True, slots=True)
class NetworkMetrics:
    received_bytes: int
    transmitted_bytes: int


@dataclass(frozen=True, slots=True)
class SystemMetrics:
    load_1m: float
    load_5m: float
    load_15m: float
    cpu_count: int
    uptime_seconds: float
    process_count: int
    memory: MemoryMetrics
    disk: DiskMetrics
    network: NetworkMetrics


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    schema_version: str
    event_id: str
    node_id: str
    observed_at: datetime
    metrics: SystemMetrics

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["observed_at"] = self.observed_at.isoformat()
        return payload

