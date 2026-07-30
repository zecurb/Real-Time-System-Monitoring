from __future__ import annotations

import unittest
from typing import Any

from fastapi.testclient import TestClient

from rtmonitor.api.app import create_app
from rtmonitor.api.config import ApiSettings
from rtmonitor.storage.memory import InMemoryEventStore


def valid_event() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "event_id": "14d6a69e-e40a-42a1-9b45-549d8a949d59",
        "node_id": "test-node-001",
        "observed_at": "2026-07-30T06:22:37.263792+00:00",
        "metrics": {
            "load_1m": 1.33,
            "load_5m": 1.08,
            "load_15m": 1.99,
            "cpu_count": 12,
            "uptime_seconds": 3223.08,
            "process_count": 329,
            "memory": {
                "total_bytes": 16_039_428_096,
                "available_bytes": 12_426_452_992,
                "used_percent": 22.53,
            },
            "disk": {
                "path": "/",
                "total_bytes": 501_863_428_096,
                "free_bytes": 447_698_452_480,
                "used_percent": 10.79,
            },
            "network": {
                "received_bytes": 2_444_071_831,
                "transmitted_bytes": 33_502_264,
            },
        },
    }


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryEventStore()
        self.client = TestClient(
            create_app(
                settings=ApiSettings(max_request_bytes=65_536),
                store=self.store,
            )
        )

    def test_liveness_and_readiness(self) -> None:
        live = self.client.get("/health/live")
        ready = self.client.get("/health/ready")

        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.json(), {"status": "ok", "storage": "unchecked"})
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json(), {"status": "ready", "storage": "available"})

    def test_readiness_fails_when_storage_is_unavailable(self) -> None:
        self.store.available = False
        response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "not_ready", "storage": "unavailable"})

    def test_accepts_valid_telemetry_with_request_id(self) -> None:
        response = self.client.post(
            "/v1/telemetry",
            json=valid_event(),
            headers={"X-Request-ID": "test-request-123"},
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "accepted")
        self.assertEqual(response.json()["request_id"], "test-request-123")
        self.assertEqual(response.json()["stored_events"], 1)
        self.assertEqual(response.headers["X-Request-ID"], "test-request-123")
        self.assertIn("X-Process-Time-Ms", response.headers)

    def test_duplicate_event_is_idempotent(self) -> None:
        first = self.client.post("/v1/telemetry", json=valid_event())
        duplicate = self.client.post("/v1/telemetry", json=valid_event())

        self.assertEqual(first.status_code, 202)
        self.assertEqual(duplicate.status_code, 202)
        self.assertEqual(duplicate.json()["status"], "duplicate")
        self.assertEqual(duplicate.json()["stored_events"], 1)

    def test_rejects_unknown_schema_version(self) -> None:
        event = valid_event()
        event["schema_version"] = "2.0"

        response = self.client.post("/v1/telemetry", json=event)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_rejects_naive_timestamp(self) -> None:
        event = valid_event()
        event["observed_at"] = "2026-07-30T06:22:37"

        response = self.client.post("/v1/telemetry", json=event)

        self.assertEqual(response.status_code, 422)

    def test_rejects_oversized_declared_body(self) -> None:
        response = self.client.post(
            "/v1/telemetry",
            content=b"{}",
            headers={"Content-Length": "70000", "Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error"]["code"], "payload_too_large")


if __name__ == "__main__":
    unittest.main()

