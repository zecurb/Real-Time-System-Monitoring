"""Bounded telemetry buffer used before durable transport is introduced."""

from __future__ import annotations

from collections import deque
from threading import Lock

from rtmonitor.api.contracts import TelemetryEventRequest


class TelemetryBuffer:
    """Thread-safe buffer that refuses events instead of silently dropping them."""

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be greater than zero")
        self._events: deque[TelemetryEventRequest] = deque()
        self._capacity = capacity
        self._lock = Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    def accept(self, event: TelemetryEventRequest) -> bool:
        with self._lock:
            if len(self._events) >= self._capacity:
                return False
            self._events.append(event)
            return True

    def size(self) -> int:
        with self._lock:
            return len(self._events)

    def is_full(self) -> bool:
        with self._lock:
            return len(self._events) >= self._capacity

