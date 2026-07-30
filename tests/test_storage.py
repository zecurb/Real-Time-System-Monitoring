from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test_api import valid_event

from rtmonitor.api.contracts import TelemetryEventRequest
from rtmonitor.storage.base import StoreResult
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
            await first_store.close()

            reopened_store = SqlAlchemyEventStore(database_url)
            self.assertTrue(await reopened_store.ping())
            self.assertEqual(await reopened_store.count(), 1)
            await reopened_store.close()


if __name__ == "__main__":
    unittest.main()
