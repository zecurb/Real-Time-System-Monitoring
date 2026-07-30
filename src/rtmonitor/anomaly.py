"""CPU-efficient, explainable anomaly scoring for telemetry time series."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

MIN_BASELINE_SAMPLES = 5
ROBUST_Z_SCALE = 0.6745
ANOMALY_THRESHOLD = 3.5
CRITICAL_THRESHOLD = 7.0

# Counters and uptime naturally increase and require rate conversion before scoring.
SCORABLE_METRICS = frozenset(
    {
        "system.load.1m",
        "system.load.5m",
        "system.load.15m",
        "system.process.count",
        "memory.used.percent",
        "disk.used.percent",
    }
)


@dataclass(frozen=True, slots=True)
class AnomalyScore:
    baseline: float
    dispersion: float
    score: float
    severity: str
    sample_count: int


def robust_anomaly_score(
    value: float,
    history: list[float],
    *,
    minimum_samples: int = MIN_BASELINE_SAMPLES,
) -> AnomalyScore | None:
    """Return a robust z-score when enough baseline data exists and value is anomalous."""
    if len(history) < minimum_samples:
        return None
    baseline = float(median(history))
    dispersion = float(median(abs(point - baseline) for point in history))
    if dispersion == 0:
        score = 0.0 if value == baseline else CRITICAL_THRESHOLD
    else:
        score = abs(ROBUST_Z_SCALE * (value - baseline) / dispersion)
    if score < ANOMALY_THRESHOLD:
        return None
    return AnomalyScore(
        baseline=baseline,
        dispersion=dispersion,
        score=score,
        severity="critical" if score >= CRITICAL_THRESHOLD else "warning",
        sample_count=len(history),
    )
