"""Desktop launcher for the self-contained Windows distribution."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Protocol

import uvicorn
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from rtmonitor.api.app import create_app
from rtmonitor.collector.linux import LinuxCollector
from rtmonitor.collector.windows import WindowsCollector
from rtmonitor.models import TelemetryEvent
from rtmonitor.pipeline.worker import PipelineWorker, WorkerSettings
from rtmonitor.storage import SqlAlchemyEventStore

LOGGER = logging.getLogger("rtmonitor.desktop")
PRODUCT_DIRECTORY = "Real-Time System Monitoring"
DEFAULT_PORT = 8765
DEFAULT_COLLECTION_INTERVAL = 5.0


class TelemetryCollector(Protocol):
    def collect(self) -> TelemetryEvent: ...


def _resource_root() -> Path:
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root is not None:
        return Path(bundled_root)
    return Path(__file__).resolve().parents[2]


def _default_data_directory() -> Path:
    if sys.platform == "win32":
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / PRODUCT_DIRECTORY
    base = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "rtmonitor"


def _database_url(data_directory: Path) -> str:
    database_path = (data_directory / "rtmonitor.db").resolve()
    return f"sqlite+aiosqlite:///{database_path.as_posix()}"


def _apply_migrations(resource_root: Path, database_url: str) -> None:
    config = Config(str(resource_root / "alembic.ini"))
    config.set_main_option("script_location", str(resource_root / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")


def _build_application(resource_root: Path) -> FastAPI:
    app = create_app()
    dashboard_directory = resource_root / "frontend" / "dist"
    if not (dashboard_directory / "index.html").is_file():
        raise RuntimeError("the bundled dashboard assets are missing")
    app.mount(
        "/",
        StaticFiles(directory=str(dashboard_directory), html=True),
        name="dashboard",
    )
    return app


def _wait_until_ready(port: int, stop_event: threading.Event) -> bool:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not stop_event.is_set():
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            stop_event.wait(0.25)
    return False


def _open_browser_when_ready(port: int, stop_event: threading.Event) -> None:
    if _wait_until_ready(port, stop_event):
        webbrowser.open(f"http://127.0.0.1:{port}")


def _create_collector() -> TelemetryCollector:
    if sys.platform == "win32":
        return WindowsCollector()
    return LinuxCollector()


def _post_event(port: int, event: TelemetryEvent) -> None:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/telemetry",
        data=json.dumps(event.as_dict()).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        if response.status != 202:
            raise RuntimeError(f"telemetry ingestion returned HTTP {response.status}")


def _run_collector(
    *,
    port: int,
    interval: float,
    stop_event: threading.Event,
) -> None:
    if not _wait_until_ready(port, stop_event):
        return
    collector = _create_collector()
    while not stop_event.is_set():
        try:
            _post_event(port, collector.collect())
        except (OSError, RuntimeError) as exc:
            LOGGER.warning("local telemetry collection failed: %s", exc)
        stop_event.wait(interval)


def _run_worker(database_url: str) -> None:
    async def run_worker() -> None:
        settings = WorkerSettings.from_environment()
        store = SqlAlchemyEventStore(database_url)
        worker = PipelineWorker(store=store, settings=settings)
        try:
            await worker.run()
        finally:
            await store.close()

    asyncio.run(run_worker())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Launch the Real-Time System Monitoring desktop dashboard"
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--data-dir", type=Path, default=_default_data_directory())
    parser.add_argument(
        "--collection-interval",
        type=float,
        default=DEFAULT_COLLECTION_INTERVAL,
        help="seconds between local telemetry snapshots",
    )
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-collector", action="store_true")
    return parser


def run() -> None:
    args = build_parser().parse_args()
    if not 1 <= args.port <= 65_535:
        raise SystemExit("--port must be between 1 and 65535")
    if args.collection_interval <= 0:
        raise SystemExit("--collection-interval must be greater than zero")

    data_directory = args.data_dir.expanduser().resolve()
    data_directory.mkdir(parents=True, exist_ok=True)
    database_url = _database_url(data_directory)
    os.environ["RTMONITOR_DATABASE_URL"] = database_url

    resource_root = _resource_root()
    _apply_migrations(resource_root, database_url)
    app = _build_application(resource_root)
    stop_event = threading.Event()

    threading.Thread(
        target=_run_worker,
        args=(database_url,),
        daemon=True,
        name="rtmonitor-worker",
    ).start()
    if not args.no_collector:
        threading.Thread(
            target=_run_collector,
            kwargs={
                "port": args.port,
                "interval": args.collection_interval,
                "stop_event": stop_event,
            },
            daemon=True,
            name="rtmonitor-collector",
        ).start()
    if not args.no_browser:
        threading.Thread(
            target=_open_browser_when_ready,
            args=(args.port, stop_event),
            daemon=True,
            name="rtmonitor-browser",
        ).start()

    try:
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=args.port,
            access_log=False,
            log_level="info",
        )
    finally:
        stop_event.set()


if __name__ == "__main__":
    run()
