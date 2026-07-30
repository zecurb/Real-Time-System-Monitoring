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
    buffer_capacity: int = 10_000
    max_request_bytes: int = 65_536

    @classmethod
    def from_environment(cls) -> ApiSettings:
        return cls(
            buffer_capacity=_positive_int("RTMONITOR_BUFFER_CAPACITY", 10_000),
            max_request_bytes=_positive_int("RTMONITOR_MAX_REQUEST_BYTES", 65_536),
        )

