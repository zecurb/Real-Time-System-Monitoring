"""Storage contracts independent of a database implementation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from rtmonitor.api.contracts import TelemetryEventRequest


class StoreResult(StrEnum):
    CREATED = "created"
    DUPLICATE = "duplicate"


class QueueStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    RETRY = "retry"
    PROCESSED = "processed"
    DEAD_LETTER = "dead_letter"


@dataclass(frozen=True, slots=True)
class QueueLease:
    event_id: str
    payload: dict[str, object]
    attempt: int


@dataclass(frozen=True, slots=True)
class QueueStats:
    pending: int = 0
    processing: int = 0
    retry: int = 0
    processed: int = 0
    dead_letter: int = 0


class EventStore(Protocol):
    async def store(self, event: TelemetryEventRequest) -> StoreResult: ...

    async def count(self) -> int: ...

    async def queue_depth(self) -> int: ...

    async def queue_stats(self) -> QueueStats: ...

    async def ping(self) -> bool: ...

    async def close(self) -> None: ...
