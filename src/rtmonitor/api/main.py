"""Executable entrypoint for the ingestion API."""

from __future__ import annotations

import uvicorn


def run() -> None:
    uvicorn.run(
        "rtmonitor.api.app:create_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
        access_log=False,
    )


if __name__ == "__main__":
    run()

