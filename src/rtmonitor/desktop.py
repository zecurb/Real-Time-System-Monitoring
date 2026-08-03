"""Desktop launcher for the self-contained Windows distribution."""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from rtmonitor.api.app import create_app

PRODUCT_DIRECTORY = "Real-Time System Monitoring"
DEFAULT_PORT = 8765


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


def _open_browser_when_ready(port: int) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                webbrowser.open(f"http://127.0.0.1:{port}")
                return
        except OSError:
            time.sleep(0.25)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Launch the Real-Time System Monitoring desktop dashboard"
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--data-dir", type=Path, default=_default_data_directory())
    parser.add_argument("--no-browser", action="store_true")
    return parser


def run() -> None:
    args = build_parser().parse_args()
    if not 1 <= args.port <= 65_535:
        raise SystemExit("--port must be between 1 and 65535")

    data_directory = args.data_dir.expanduser().resolve()
    data_directory.mkdir(parents=True, exist_ok=True)
    database_url = _database_url(data_directory)
    os.environ["RTMONITOR_DATABASE_URL"] = database_url

    resource_root = _resource_root()
    _apply_migrations(resource_root, database_url)
    app = _build_application(resource_root)

    if not args.no_browser:
        threading.Thread(
            target=_open_browser_when_ready,
            args=(args.port,),
            daemon=True,
        ).start()

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=args.port,
        access_log=False,
        log_level="info",
    )


if __name__ == "__main__":
    run()
