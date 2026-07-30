"""In-memory event store for tests; never use as production durability."""

from __future__ import annotations

from datetime import datetime

from rtmonitor.api.contracts import TelemetryEventRequest
from rtmonitor.storage.base import MetricSample, NodeSummary, QueueStats, StoreResult


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

    async def queue_depth(self) -> int:
        return len(self._event_ids)

    async def queue_stats(self) -> QueueStats:
        return QueueStats(pending=len(self._event_ids))

    async def query_metric_samples(
        self,
        *,
        node_id: str,
        metric_name: str,
        start: datetime,
        end: datetime,
        limit: int,
        cursor: tuple[datetime, str] | None = None,
    ) -> list[MetricSample]:
        return []

    async def list_nodes(self, *, limit: int) -> list[NodeSummary]:
        return []

    async def ping(self) -> bool:
        return self.available

    async def close(self) -> None:
        return None
