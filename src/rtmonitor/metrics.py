"""Normalized metric definitions shared by processing and presentation."""

from __future__ import annotations

from dataclasses import dataclass

from rtmonitor.api.contracts import TelemetryEventRequest


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    name: str
    display_name: str
    unit: str
    category: str


METRIC_DEFINITIONS = (
    MetricDefinition("system.load.1m", "Load average (1m)", "load", "System"),
    MetricDefinition("system.load.5m", "Load average (5m)", "load", "System"),
    MetricDefinition("system.load.15m", "Load average (15m)", "load", "System"),
    MetricDefinition("system.cpu.count", "CPU cores", "count", "System"),
    MetricDefinition("system.uptime.seconds", "Uptime", "seconds", "System"),
    MetricDefinition("system.process.count", "Processes", "count", "System"),
    MetricDefinition("memory.total.bytes", "Memory total", "bytes", "Memory"),
    MetricDefinition("memory.available.bytes", "Memory available", "bytes", "Memory"),
    MetricDefinition("memory.used.percent", "Memory used", "percent", "Memory"),
    MetricDefinition("disk.total.bytes", "Disk total", "bytes", "Disk"),
    MetricDefinition("disk.free.bytes", "Disk free", "bytes", "Disk"),
    MetricDefinition("disk.used.percent", "Disk used", "percent", "Disk"),
    MetricDefinition("network.received.bytes", "Network received", "bytes", "Network"),
    MetricDefinition(
        "network.transmitted.bytes",
        "Network transmitted",
        "bytes",
        "Network",
    ),
)


def metric_values(event: TelemetryEventRequest) -> dict[str, float]:
    metrics = event.metrics
    return {
        "system.load.1m": float(metrics.load_1m),
        "system.load.5m": float(metrics.load_5m),
        "system.load.15m": float(metrics.load_15m),
        "system.cpu.count": float(metrics.cpu_count),
        "system.uptime.seconds": float(metrics.uptime_seconds),
        "system.process.count": float(metrics.process_count),
        "memory.total.bytes": float(metrics.memory.total_bytes),
        "memory.available.bytes": float(metrics.memory.available_bytes),
        "memory.used.percent": float(metrics.memory.used_percent),
        "disk.total.bytes": float(metrics.disk.total_bytes),
        "disk.free.bytes": float(metrics.disk.free_bytes),
        "disk.used.percent": float(metrics.disk.used_percent),
        "network.received.bytes": float(metrics.network.received_bytes),
        "network.transmitted.bytes": float(metrics.network.transmitted_bytes),
    }
