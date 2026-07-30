"""Linux telemetry collection using stable kernel interfaces."""

from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from rtmonitor.models import (
    DiskMetrics,
    MemoryMetrics,
    NetworkMetrics,
    SystemMetrics,
    TelemetryEvent,
)


class CollectionError(RuntimeError):
    """Raised when required host telemetry cannot be collected safely."""


class LinuxCollector:
    """Collect a privacy-conscious snapshot from Linux procfs."""

    def __init__(
        self,
        *,
        proc_root: Path = Path("/proc"),
        disk_path: Path = Path("/"),
        node_id: str | None = None,
    ) -> None:
        self._proc_root = proc_root
        self._disk_path = disk_path
        self._node_id = node_id or self._anonymous_node_id()

    def collect(self) -> TelemetryEvent:
        try:
            load_1m, load_5m, load_15m = self._read_load_average()
            metrics = SystemMetrics(
                load_1m=load_1m,
                load_5m=load_5m,
                load_15m=load_15m,
                cpu_count=os.cpu_count() or 1,
                uptime_seconds=self._read_uptime(),
                process_count=self._count_processes(),
                memory=self._read_memory(),
                disk=self._read_disk(),
                network=self._read_network(),
            )
        except (OSError, ValueError, KeyError) as exc:
            raise CollectionError(f"telemetry collection failed: {exc}") from exc

        return TelemetryEvent(
            schema_version="1.0",
            event_id=str(uuid.uuid4()),
            node_id=self._node_id,
            observed_at=datetime.now(UTC),
            metrics=metrics,
        )

    def _read_load_average(self) -> tuple[float, float, float]:
        fields = (self._proc_root / "loadavg").read_text(encoding="utf-8").split()
        if len(fields) < 3:
            raise ValueError("invalid loadavg data")
        return float(fields[0]), float(fields[1]), float(fields[2])

    def _read_uptime(self) -> float:
        return float((self._proc_root / "uptime").read_text(encoding="utf-8").split()[0])

    def _count_processes(self) -> int:
        return sum(entry.name.isdigit() for entry in self._proc_root.iterdir())

    def _read_memory(self) -> MemoryMetrics:
        values: dict[str, int] = {}
        for line in (self._proc_root / "meminfo").read_text(encoding="utf-8").splitlines():
            key, raw_value = line.split(":", maxsplit=1)
            value_kib = int(raw_value.strip().split()[0])
            values[key] = value_kib * 1024

        total = values["MemTotal"]
        available = values["MemAvailable"]
        used_percent = round(((total - available) / total) * 100, 2) if total else 0.0
        return MemoryMetrics(total, available, used_percent)

    def _read_disk(self) -> DiskMetrics:
        usage = shutil.disk_usage(self._disk_path)
        used_percent = round(((usage.total - usage.free) / usage.total) * 100, 2)
        return DiskMetrics(str(self._disk_path), usage.total, usage.free, used_percent)

    def _read_network(self) -> NetworkMetrics:
        received = 0
        transmitted = 0
        lines = (self._proc_root / "net/dev").read_text(encoding="utf-8").splitlines()[2:]
        for line in lines:
            _, raw_stats = line.split(":", maxsplit=1)
            stats = raw_stats.split()
            received += int(stats[0])
            transmitted += int(stats[8])
        return NetworkMetrics(received, transmitted)

    @staticmethod
    def _anonymous_node_id() -> str:
        machine_id_path = Path("/etc/machine-id")
        if machine_id_path.exists():
            raw_id = machine_id_path.read_text(encoding="utf-8").strip()
        else:
            raw_id = str(uuid.uuid4())
        return hashlib.sha256(raw_id.encode()).hexdigest()[:16]
