"""Storage contracts independent of a database implementation."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from rtmonitor.api.contracts import TelemetryEventRequest


class StoreResult(StrEnum):
    CREATED = "created"
    DUPLICATE = "duplicate"


class EventStore(Protocol):
    async def store(self, event: TelemetryEventRequest) -> StoreResult: ...

    async def count(self) -> int: ...

    async def ping(self) -> bool: ...

    async def close(self) -> None: ...

