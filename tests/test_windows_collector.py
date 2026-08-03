from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rtmonitor.collector.windows import WindowsCollector


class WindowsCollectorTests(unittest.TestCase):
    def test_collects_expected_windows_metrics(self) -> None:
        collector = WindowsCollector(disk_path=Path("C:/"), node_id="windows-node")

        with (
            patch("rtmonitor.collector.windows.psutil.getloadavg", return_value=(1.0, 2.0, 3.0)),
            patch(
                "rtmonitor.collector.windows.psutil.virtual_memory",
                return_value=SimpleNamespace(total=16_000, available=6_000, percent=62.5),
            ),
            patch(
                "rtmonitor.collector.windows.psutil.disk_usage",
                return_value=SimpleNamespace(total=100_000, free=40_000, percent=60.0),
            ),
            patch(
                "rtmonitor.collector.windows.psutil.net_io_counters",
                return_value=SimpleNamespace(bytes_recv=1234, bytes_sent=5678),
            ),
            patch("rtmonitor.collector.windows.psutil.boot_time", return_value=100.0),
            patch("rtmonitor.collector.windows.psutil.cpu_count", return_value=8),
            patch("rtmonitor.collector.windows.psutil.pids", return_value=[1, 2, 3]),
            patch("rtmonitor.collector.windows.time.time", return_value=1000.0),
        ):
            event = collector.collect()

        self.assertEqual(event.node_id, "windows-node")
        self.assertEqual(event.metrics.cpu_count, 8)
        self.assertEqual(event.metrics.uptime_seconds, 900.0)
        self.assertEqual(event.metrics.process_count, 3)
        self.assertEqual(event.metrics.memory.used_percent, 62.5)
        self.assertEqual(event.metrics.disk.used_percent, 60.0)
        self.assertEqual(event.metrics.network.received_bytes, 1234)
        self.assertEqual(event.metrics.network.transmitted_bytes, 5678)


if __name__ == "__main__":
    unittest.main()
