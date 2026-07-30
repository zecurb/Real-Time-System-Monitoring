from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rtmonitor.collector.linux import LinuxCollector


class LinuxCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.proc_root = Path(self.temp_dir.name)
        (self.proc_root / "net").mkdir()
        (self.proc_root / "123").mkdir()
        (self.proc_root / "456").mkdir()
        (self.proc_root / "not-a-process").mkdir()
        (self.proc_root / "loadavg").write_text("1.25 0.75 0.50 1/100 123\n")
        (self.proc_root / "uptime").write_text("3600.50 7200.00\n")
        (self.proc_root / "meminfo").write_text(
            "MemTotal:       1000 kB\nMemAvailable:    250 kB\n"
        )
        (self.proc_root / "net/dev").write_text(
            "Inter-| Receive | Transmit\n"
            " face |bytes packets errs drop fifo frame compressed multicast|"
            "bytes packets errs drop fifo colls carrier compressed\n"
            "eth0: 100 1 0 0 0 0 0 0 200 2 0 0 0 0 0 0\n"
            "lo: 50 1 0 0 0 0 0 0 50 1 0 0 0 0 0 0\n"
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_collects_versioned_snapshot(self) -> None:
        event = LinuxCollector(
            proc_root=self.proc_root,
            disk_path=self.proc_root,
            node_id="test-node",
        ).collect()

        self.assertEqual(event.schema_version, "1.0")
        self.assertEqual(event.node_id, "test-node")
        self.assertEqual(event.metrics.load_1m, 1.25)
        self.assertEqual(event.metrics.uptime_seconds, 3600.5)
        self.assertEqual(event.metrics.process_count, 2)
        self.assertEqual(event.metrics.memory.total_bytes, 1_024_000)
        self.assertEqual(event.metrics.memory.available_bytes, 256_000)
        self.assertEqual(event.metrics.memory.used_percent, 75.0)
        self.assertEqual(event.metrics.network.received_bytes, 150)
        self.assertEqual(event.metrics.network.transmitted_bytes, 250)


if __name__ == "__main__":
    unittest.main()

