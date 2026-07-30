"""Opaque cursor helpers for stable metric pagination."""

from __future__ import annotations

import base64
import json
from datetime import datetime

from rtmonitor.storage import MetricSample


def encode_metric_cursor(sample: MetricSample) -> str:
    payload = json.dumps(
        {
            "observed_at": sample.observed_at.isoformat(),
            "event_id": sample.event_id,
        },
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_metric_cursor(value: str) -> tuple[datetime, str]:
    try:
        padding = "=" * (-len(value) % 4)
        raw = base64.urlsafe_b64decode(value + padding)
        payload = json.loads(raw)
        observed_at = datetime.fromisoformat(payload["observed_at"])
        event_id = str(payload["event_id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid metric cursor") from exc
    if observed_at.tzinfo is None or observed_at.utcoffset() is None or not event_id:
        raise ValueError("invalid metric cursor")
    return observed_at, event_id
