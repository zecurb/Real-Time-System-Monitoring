"""Bounded retention cleanup for normalized metric samples."""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import UTC, datetime, timedelta

from rtmonitor.api.config import ApiSettings
from rtmonitor.api.logging import configure_logging, log_event
from rtmonitor.storage import SqlAlchemyEventStore

LOGGER = logging.getLogger("rtmonitor.retention")


def _positive(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prune expired metric samples in batches")
    parser.add_argument("--days", type=_positive, default=30)
    parser.add_argument("--batch-size", type=_positive, default=10_000)
    parser.add_argument("--max-batches", type=_positive, default=10)
    return parser


async def _run(*, days: int, batch_size: int, max_batches: int) -> int:
    settings = ApiSettings.from_environment()
    store = SqlAlchemyEventStore(settings.database_url)
    cutoff = datetime.now(UTC) - timedelta(days=days)
    deleted_total = 0
    try:
        for _ in range(max_batches):
            deleted = await store.prune_metric_samples(
                before=cutoff,
                batch_size=batch_size,
            )
            deleted_total += deleted
            if deleted < batch_size:
                break
    finally:
        await store.close()
    log_event(
        LOGGER,
        "retention_complete",
        {
            "cutoff": cutoff.isoformat(),
            "deleted_samples": deleted_total,
            "batch_size": batch_size,
            "max_batches": max_batches,
        },
    )
    return deleted_total


def run() -> None:
    configure_logging()
    args = build_parser().parse_args()
    asyncio.run(
        _run(
            days=args.days,
            batch_size=args.batch_size,
            max_batches=args.max_batches,
        )
    )


if __name__ == "__main__":
    run()
