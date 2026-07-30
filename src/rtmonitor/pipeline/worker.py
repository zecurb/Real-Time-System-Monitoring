"""Lease-based worker for durable telemetry processing."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from rtmonitor.api.logging import log_event
from rtmonitor.storage import QueueLease, QueueStatus, SqlAlchemyEventStore

LOGGER = logging.getLogger("rtmonitor.pipeline")
Processor = Callable[[dict[str, object]], Awaitable[None]]


def _positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True, slots=True)
class WorkerSettings:
    database_url: str = "sqlite+aiosqlite:///./rtmonitor.db"
    batch_size: int = 100
    lease_seconds: int = 30
    poll_interval_seconds: int = 2
    max_attempts: int = 5
    retry_base_seconds: int = 5

    @classmethod
    def from_environment(cls) -> WorkerSettings:
        database_url = os.getenv(
            "RTMONITOR_DATABASE_URL",
            "sqlite+aiosqlite:///./rtmonitor.db",
        ).strip()
        if not database_url:
            raise ValueError("RTMONITOR_DATABASE_URL must not be empty")
        return cls(
            database_url=database_url,
            batch_size=_positive_int("RTMONITOR_WORKER_BATCH_SIZE", 100),
            lease_seconds=_positive_int("RTMONITOR_WORKER_LEASE_SECONDS", 30),
            poll_interval_seconds=_positive_int("RTMONITOR_WORKER_POLL_SECONDS", 2),
            max_attempts=_positive_int("RTMONITOR_WORKER_MAX_ATTEMPTS", 5),
            retry_base_seconds=_positive_int("RTMONITOR_WORKER_RETRY_BASE_SECONDS", 5),
        )


class PipelineWorker:
    def __init__(
        self,
        *,
        store: SqlAlchemyEventStore,
        settings: WorkerSettings,
        processor: Processor | None = None,
        worker_id: str | None = None,
    ) -> None:
        self._store = store
        self._settings = settings
        self._processor = processor or self._store.write_metric_samples
        self.worker_id = worker_id or f"{socket.gethostname()}-{uuid.uuid4().hex[:12]}"

    async def process_batch(self) -> int:
        leases = await self._store.claim(
            worker_id=self.worker_id,
            batch_size=self._settings.batch_size,
            lease_seconds=self._settings.lease_seconds,
        )
        for lease in leases:
            await self._process(lease)
        if leases:
            log_event(
                LOGGER,
                "pipeline_batch",
                {
                    "worker_id": self.worker_id,
                    "claimed_events": len(leases),
                    "queue_depth": await self._store.queue_depth(),
                },
            )
        return len(leases)

    async def _process(self, lease: QueueLease) -> None:
        try:
            await self._processor(lease.payload)
        except Exception as exc:
            retry_delay = self._settings.retry_base_seconds * (2 ** (lease.attempt - 1))
            outcome = await self._store.fail(
                event_id=lease.event_id,
                worker_id=self.worker_id,
                error=f"{type(exc).__name__}: {exc}",
                max_attempts=self._settings.max_attempts,
                retry_delay_seconds=retry_delay,
            )
            log_event(
                LOGGER,
                "pipeline_failed",
                {
                    "worker_id": self.worker_id,
                    "event_id": lease.event_id,
                    "attempt": lease.attempt,
                    "outcome": outcome or QueueStatus.PROCESSING,
                },
            )
            return

        completed = await self._store.complete(
            event_id=lease.event_id,
            worker_id=self.worker_id,
        )
        log_event(
            LOGGER,
            "pipeline_processed",
            {
                "worker_id": self.worker_id,
                "event_id": lease.event_id,
                "attempt": lease.attempt,
                "completed": completed,
            },
        )

    async def run(self) -> None:
        while True:
            processed = await self.process_batch()
            if processed == 0:
                await asyncio.sleep(self._settings.poll_interval_seconds)
