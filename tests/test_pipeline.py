from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from test_api import valid_event

from rtmonitor.api.contracts import TelemetryEventRequest
from rtmonitor.api.pagination import decode_metric_cursor, encode_metric_cursor
from rtmonitor.pipeline.worker import PipelineWorker, WorkerSettings
from rtmonitor.storage import QueueStatus, SqlAlchemyEventStore


class PipelineWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_worker_processes_a_durable_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            database_path = Path(temp_directory) / "telemetry.db"
            store = SqlAlchemyEventStore(f"sqlite+aiosqlite:///{database_path}")
            await store.create_schema_for_tests()
            event = TelemetryEventRequest.model_validate(valid_event())
            await store.store(event)
            processed_ids: list[str] = []

            async def processor(payload: dict[str, object]) -> None:
                processed_ids.append(str(payload["event_id"]))

            worker = PipelineWorker(
                store=store,
                settings=WorkerSettings(batch_size=10),
                processor=processor,
                worker_id="test-worker",
            )

            self.assertEqual(await worker.process_batch(), 1)
            self.assertEqual(processed_ids, [str(event.event_id)])
            self.assertEqual(
                await store.queue_status(str(event.event_id)),
                QueueStatus.PROCESSED,
            )
            self.assertEqual(await store.queue_depth(), 0)
            await store.close()

    async def test_default_processor_normalizes_metrics_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            database_path = Path(temp_directory) / "telemetry.db"
            store = SqlAlchemyEventStore(f"sqlite+aiosqlite:///{database_path}")
            await store.create_schema_for_tests()
            event = TelemetryEventRequest.model_validate(valid_event())
            await store.store(event)
            worker = PipelineWorker(
                store=store,
                settings=WorkerSettings(batch_size=10),
                worker_id="normalizer",
            )

            self.assertEqual(await worker.process_batch(), 1)
            await store.write_metric_samples(event.model_dump(mode="json"))
            samples = await store.query_metric_samples(
                node_id=event.node_id,
                metric_name="memory.used.percent",
                start=event.observed_at - timedelta(minutes=1),
                end=event.observed_at + timedelta(minutes=1),
                limit=10,
            )

            self.assertEqual(len(samples), 1)
            self.assertEqual(samples[0].value, 22.53)
            self.assertEqual(samples[0].event_id, str(event.event_id))
            nodes = await store.list_nodes(limit=100)
            self.assertEqual(len(nodes), 1)
            self.assertEqual(nodes[0].node_id, event.node_id)
            self.assertEqual(nodes[0].event_count, 1)
            await store.close()

    async def test_default_processor_detects_explainable_anomaly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            database_path = Path(temp_directory) / "telemetry.db"
            store = SqlAlchemyEventStore(f"sqlite+aiosqlite:///{database_path}")
            await store.create_schema_for_tests()
            start = datetime(2026, 7, 30, 6, 0, tzinfo=UTC)
            for index, memory_used in enumerate((20.0, 21.0, 22.0, 23.0, 24.0, 90.0)):
                payload = valid_event()
                payload["event_id"] = f"{index + 1}4d6a69e-e40a-42a1-9b45-549d8a949d59"
                payload["observed_at"] = (start + timedelta(minutes=index)).isoformat()
                payload["metrics"]["memory"]["used_percent"] = memory_used
                event = TelemetryEventRequest.model_validate(payload)
                await store.store(event)
                worker = PipelineWorker(
                    store=store,
                    settings=WorkerSettings(batch_size=1),
                    worker_id=f"detector-{index}",
                )
                self.assertEqual(await worker.process_batch(), 1)

            findings = await store.list_anomalies(
                node_id="test-node-001",
                start=start,
                end=start + timedelta(hours=1),
                limit=100,
            )
            memory_findings = [
                finding
                for finding in findings
                if finding.metric_name == "memory.used.percent"
            ]
            self.assertEqual(len(memory_findings), 1)
            self.assertEqual(memory_findings[0].value, 90.0)
            self.assertEqual(memory_findings[0].baseline, 22.0)
            self.assertEqual(memory_findings[0].severity, "critical")
            self.assertEqual(memory_findings[0].sample_count, 5)
            await store.close()

    async def test_metric_query_uses_stable_cursor_pagination(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            database_path = Path(temp_directory) / "telemetry.db"
            store = SqlAlchemyEventStore(f"sqlite+aiosqlite:///{database_path}")
            await store.create_schema_for_tests()
            start = datetime(2026, 7, 30, 6, 0, tzinfo=UTC)
            for index in range(3):
                payload = valid_event()
                payload["event_id"] = f"{index + 1}4d6a69e-e40a-42a1-9b45-549d8a949d59"
                payload["observed_at"] = (start + timedelta(minutes=index)).isoformat()
                event = TelemetryEventRequest.model_validate(payload)
                await store.store(event)
                await store.write_metric_samples(event.model_dump(mode="json"))

            first_page = await store.query_metric_samples(
                node_id="test-node-001",
                metric_name="system.load.1m",
                start=start,
                end=start + timedelta(hours=1),
                limit=2,
            )
            cursor = decode_metric_cursor(encode_metric_cursor(first_page[-1]))
            second_page = await store.query_metric_samples(
                node_id="test-node-001",
                metric_name="system.load.1m",
                start=start,
                end=start + timedelta(hours=1),
                limit=2,
                cursor=cursor,
            )

            self.assertEqual(len(first_page), 2)
            self.assertEqual(len(second_page), 1)
            self.assertNotIn(second_page[0].event_id, {item.event_id for item in first_page})
            await store.close()

    async def test_retention_prunes_only_expired_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            database_path = Path(temp_directory) / "telemetry.db"
            store = SqlAlchemyEventStore(f"sqlite+aiosqlite:///{database_path}")
            await store.create_schema_for_tests()
            cutoff = datetime(2026, 7, 15, tzinfo=UTC)
            events: list[TelemetryEventRequest] = []
            for event_id, observed_at in (
                ("14d6a69e-e40a-42a1-9b45-549d8a949d59", cutoff - timedelta(days=1)),
                ("24d6a69e-e40a-42a1-9b45-549d8a949d59", cutoff + timedelta(days=1)),
            ):
                payload = valid_event()
                payload["event_id"] = event_id
                payload["observed_at"] = observed_at.isoformat()
                event = TelemetryEventRequest.model_validate(payload)
                events.append(event)
                await store.store(event)
                await store.write_metric_samples(event.model_dump(mode="json"))

            self.assertEqual(
                await store.prune_metric_samples(before=cutoff, batch_size=100),
                14,
            )
            remaining = await store.query_metric_samples(
                node_id="test-node-001",
                metric_name="memory.used.percent",
                start=cutoff,
                end=cutoff + timedelta(days=2),
                limit=10,
            )
            self.assertEqual([sample.event_id for sample in remaining], [str(events[1].event_id)])
            await store.close()


if __name__ == "__main__":
    unittest.main()
