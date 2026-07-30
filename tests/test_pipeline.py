from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test_api import valid_event

from rtmonitor.api.contracts import TelemetryEventRequest
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


if __name__ == "__main__":
    unittest.main()
