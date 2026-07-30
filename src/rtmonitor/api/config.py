"""Runtime configuration for the ingestion API."""

from __future__ import annotations

import os
from dataclasses import dataclass


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
class ApiSettings:
    max_request_bytes: int = 65_536
    database_url: str = "sqlite+aiosqlite:///./rtmonitor.db"

    @classmethod
    def from_environment(cls) -> ApiSettings:
        database_url = os.getenv(
            "RTMONITOR_DATABASE_URL",
            "sqlite+aiosqlite:///./rtmonitor.db",
        ).strip()
        if not database_url:
            raise ValueError("RTMONITOR_DATABASE_URL must not be empty")
        return cls(
            max_request_bytes=_positive_int("RTMONITOR_MAX_REQUEST_BYTES", 65_536),
            database_url=database_url,
        )
