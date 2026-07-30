"""Executable entrypoint for the durable pipeline worker."""

from __future__ import annotations

import argparse
import asyncio

from rtmonitor.api.logging import configure_logging
from rtmonitor.pipeline.worker import PipelineWorker, WorkerSettings
from rtmonitor.storage import SqlAlchemyEventStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Process durable telemetry queue entries")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process one available batch and exit",
    )
    return parser


async def _run(*, once: bool) -> None:
    configure_logging()
    settings = WorkerSettings.from_environment()
    store = SqlAlchemyEventStore(settings.database_url)
    worker = PipelineWorker(store=store, settings=settings)
    try:
        if once:
            await worker.process_batch()
        else:
            await worker.run()
    finally:
        await store.close()


def run() -> None:
    args = build_parser().parse_args()
    try:
        asyncio.run(_run(once=args.once))
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    run()
