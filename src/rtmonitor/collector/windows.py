"""Windows telemetry collection using psutil and stable OS identifiers."""

from __future__ import annotations

import hashlib
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psutil

from rtmonitor.collector.linux import CollectionError
from rtmonitor.models import (
    DiskMetrics,
    MemoryMetrics,
    NetworkMetrics,
    SystemMetrics,
    TelemetryEvent,
)


class WindowsCollector:
    """Collect a privacy-conscious telemetry snapshot from Windows."""

    def __init__(
        self,
        *,
        disk_path: Path | None = None,
        node_id: str | None = None,
    ) -> None:
        system_drive = os.getenv("SystemDrive", "C:")
        self._disk_path = disk_path or Path(f"{system_drive}\\")
        self._node_id = node_id or self._anonymous_node_id()

    def collect(self) -> TelemetryEvent:
        try:
            load_1m, load_5m, load_15m = psutil.getloadavg()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(str(self._disk_path))
            network = psutil.net_io_counters()
            uptime_seconds = max(0.0, time.time() - psutil.boot_time())
            metrics = SystemMetrics(
                load_1m=float(load_1m),
                load_5m=float(load_5m),
                load_15m=float(load_15m),
                cpu_count=psutil.cpu_count(logical=True) or os.cpu_count() or 1,
                uptime_seconds=uptime_seconds,
                process_count=len(psutil.pids()),
                memory=MemoryMetrics(
                    total_bytes=int(memory.total),
                    available_bytes=int(memory.available),
                    used_percent=round(float(memory.percent), 2),
                ),
                disk=DiskMetrics(
                    path=str(self._disk_path),
                    total_bytes=int(disk.total),
                    free_bytes=int(disk.free),
                    used_percent=round(float(disk.percent), 2),
                ),
                network=NetworkMetrics(
                    received_bytes=int(network.bytes_recv),
                    transmitted_bytes=int(network.bytes_sent),
                ),
            )
        except (OSError, ValueError, psutil.Error) as exc:
            raise CollectionError(f"telemetry collection failed: {exc}") from exc

        return TelemetryEvent(
            schema_version="1.0",
            event_id=str(uuid.uuid4()),
            node_id=self._node_id,
            observed_at=datetime.now(UTC),
            metrics=metrics,
        )

    @staticmethod
    def _anonymous_node_id() -> str:
        if sys.platform != "win32":
            raw_id = str(uuid.getnode())
        else:
            import winreg

            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Cryptography",
                ) as key:
                    raw_id, _ = winreg.QueryValueEx(key, "MachineGuid")
            except OSError:
                raw_id = str(uuid.getnode())
        return hashlib.sha256(str(raw_id).encode()).hexdigest()[:16]
