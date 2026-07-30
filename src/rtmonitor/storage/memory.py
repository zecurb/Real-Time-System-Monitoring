"""In-memory event store for tests; never use as production durability."""

from __future__ import annotations

from rtmonitor.api.contracts import TelemetryEventRequest
from rtmonitor.storage.base import StoreResult


class InMemoryEventStore:
    def __init__(self) -> None:
        self._event_ids: set[str] = set()
        self.available = True

    async def store(self, event: TelemetryEventRequest) -> StoreResult:
        event_id = str(event.event_id)
        if event_id in self._event_ids:
            return StoreResult.DUPLICATE
        self._event_ids.add(event_id)
        return StoreResult.CREATED

    async def count(self) -> int:
        return len(self._event_ids)

    async def ping(self) -> bool:
        return self.available

    async def close(self) -> None:
        return None

