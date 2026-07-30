from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test_api import valid_event

from rtmonitor.api.contracts import TelemetryEventRequest
from rtmonitor.storage.base import QueueStatus, StoreResult
from rtmonitor.storage.sqlalchemy import SqlAlchemyEventStore


class SqlAlchemyEventStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_event_survives_store_restart_and_duplicates_are_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            database_path = Path(temp_directory) / "telemetry.db"
            database_url = f"sqlite+aiosqlite:///{database_path}"
            event = TelemetryEventRequest.model_validate(valid_event())

            first_store = SqlAlchemyEventStore(database_url)
            await first_store.create_schema_for_tests()
            self.assertEqual(await first_store.store(event), StoreResult.CREATED)
            self.assertEqual(await first_store.store(event), StoreResult.DUPLICATE)
            self.assertEqual(await first_store.count(), 1)
            self.assertEqual(await first_store.queue_depth(), 1)
            await first_store.close()

            reopened_store = SqlAlchemyEventStore(database_url)
            self.assertTrue(await reopened_store.ping())
            self.assertEqual(await reopened_store.count(), 1)
            await reopened_store.close()

    async def test_workers_claim_disjoint_batches_and_complete_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            database_path = Path(temp_directory) / "telemetry.db"
            store = SqlAlchemyEventStore(f"sqlite+aiosqlite:///{database_path}")
            await store.create_schema_for_tests()
            first_data = valid_event()
            second_data = valid_event()
            second_data["event_id"] = "24d6a69e-e40a-42a1-9b45-549d8a949d59"
            await store.store(TelemetryEventRequest.model_validate(first_data))
            await store.store(TelemetryEventRequest.model_validate(second_data))

            first_claim = await store.claim(
                worker_id="worker-a",
                batch_size=1,
                lease_seconds=30,
            )
            second_claim = await store.claim(
                worker_id="worker-b",
                batch_size=1,
                lease_seconds=30,
            )

            self.assertEqual(len(first_claim), 1)
            self.assertEqual(len(second_claim), 1)
            self.assertNotEqual(first_claim[0].event_id, second_claim[0].event_id)
            self.assertTrue(
                await store.complete(event_id=first_claim[0].event_id, worker_id="worker-a")
            )
            self.assertTrue(
                await store.complete(event_id=second_claim[0].event_id, worker_id="worker-b")
            )
            self.assertEqual(await store.queue_depth(), 0)
            stats = await store.queue_stats()
            self.assertEqual(stats.processed, 2)
            await store.close()

    async def test_expired_lease_is_recovered_and_failures_dead_letter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            database_path = Path(temp_directory) / "telemetry.db"
            store = SqlAlchemyEventStore(f"sqlite+aiosqlite:///{database_path}")
            await store.create_schema_for_tests()
            event = TelemetryEventRequest.model_validate(valid_event())
            await store.store(event)

            abandoned = await store.claim(
                worker_id="crashed-worker",
                batch_size=1,
                lease_seconds=0,
            )
            recovered = await store.claim(
                worker_id="replacement-worker",
                batch_size=1,
                lease_seconds=30,
            )
            self.assertEqual(abandoned[0].event_id, recovered[0].event_id)
            self.assertEqual(recovered[0].attempt, 2)

            outcome = await store.fail(
                event_id=recovered[0].event_id,
                worker_id="replacement-worker",
                error="processor failed",
                max_attempts=2,
                retry_delay_seconds=0,
            )
            self.assertEqual(outcome, QueueStatus.DEAD_LETTER)
            self.assertEqual(
                await store.queue_status(recovered[0].event_id),
                QueueStatus.DEAD_LETTER,
            )
            self.assertEqual(await store.queue_depth(), 0)
            stats = await store.queue_stats()
            self.assertEqual(stats.dead_letter, 1)
            await store.close()


if __name__ == "__main__":
    unittest.main()
