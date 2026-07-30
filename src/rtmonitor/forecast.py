"""Explainable resource threshold forecasting and deterministic backtesting."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from rtmonitor.execution import ExecutionProvider, resolve_execution_provider

MIN_FORECAST_SAMPLES = 6
MIN_SPAN_SECONDS = 300.0
MIN_R_SQUARED = 0.60
MAX_HORIZON_HOURS = 24.0 * 7

FORECAST_THRESHOLDS = {
    "memory.used.percent": 90.0,
    "disk.used.percent": 90.0,
}


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    observed_at: datetime
    value: float


@dataclass(frozen=True, slots=True)
class ResourceForecast:
    current_value: float
    threshold: float
    slope_per_hour: float
    hours_to_threshold: float
    predicted_at: datetime
    r_squared: float
    confidence: str
    risk: str
    sample_count: int
    backtest_error: float | None
    provider: str
    fallback_reason: str | None


@dataclass(frozen=True, slots=True)
class _LinearFit:
    slope: float
    intercept: float
    r_squared: float


def _fit_cpu(xs: list[float], ys: list[float]) -> _LinearFit | None:
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((value - mean_x) ** 2 for value in xs)
    if denominator == 0:
        return None
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    slope /= denominator
    intercept = mean_y - slope * mean_x
    predictions = [intercept + slope * x for x in xs]
    residual = sum(
        (actual - predicted) ** 2
        for actual, predicted in zip(ys, predictions, strict=True)
    )
    total = sum((actual - mean_y) ** 2 for actual in ys)
    r_squared = 1.0 if total == 0 else max(0.0, 1.0 - residual / total)
    return _LinearFit(slope, intercept, r_squared)


def _scalar(value: Any) -> float:
    item = value.item() if hasattr(value, "item") else value
    return float(item)


def _fit_gpu(xs: list[float], ys: list[float]) -> _LinearFit | None:
    """Run the regression math on a CUDA device through optional CuPy."""
    cupy: Any = importlib.import_module("cupy")
    x_values = cupy.asarray(xs, dtype=cupy.float64)
    y_values = cupy.asarray(ys, dtype=cupy.float64)
    mean_x = cupy.mean(x_values)
    mean_y = cupy.mean(y_values)
    denominator = cupy.sum((x_values - mean_x) ** 2)
    if _scalar(denominator) == 0:
        return None
    slope = cupy.sum((x_values - mean_x) * (y_values - mean_y)) / denominator
    intercept = mean_y - slope * mean_x
    predictions = intercept + slope * x_values
    residual = cupy.sum((y_values - predictions) ** 2)
    total = cupy.sum((y_values - mean_y) ** 2)
    total_value = _scalar(total)
    r_squared = (
        1.0
        if total_value == 0
        else max(0.0, 1.0 - _scalar(residual) / total_value)
    )
    return _LinearFit(_scalar(slope), _scalar(intercept), r_squared)


def _fit_with_provider(
    xs: list[float],
    ys: list[float],
    provider: ExecutionProvider,
) -> tuple[_LinearFit | None, ExecutionProvider]:
    if provider.active == "cpu":
        return _fit_cpu(xs, ys), provider
    try:
        return _fit_gpu(xs, ys), provider
    except Exception as exc:
        fallback = ExecutionProvider(
            requested=provider.requested,
            active="cpu",
            accelerator=None,
            fallback_reason=f"GPU regression failed; CPU fallback used: {exc}",
        )
        return _fit_cpu(xs, ys), fallback


def forecast_threshold(
    points: list[ForecastPoint],
    *,
    threshold: float,
    minimum_samples: int = MIN_FORECAST_SAMPLES,
    provider: ExecutionProvider | None = None,
) -> ResourceForecast | None:
    """Fit a least-squares trend and forecast an upward threshold crossing."""
    if len(points) < minimum_samples:
        return None
    ordered = sorted(points, key=lambda point: point.observed_at)
    origin = ordered[0].observed_at
    xs = [(point.observed_at - origin).total_seconds() / 3600.0 for point in ordered]
    ys = [point.value for point in ordered]
    if xs[-1] * 3600.0 < MIN_SPAN_SECONDS:
        return None

    selected_provider = provider or resolve_execution_provider("cpu")
    fit, active_provider = _fit_with_provider(xs, ys, selected_provider)
    if fit is None:
        return None
    slope = fit.slope
    if slope <= 0:
        return None
    r_squared = fit.r_squared
    if r_squared < MIN_R_SQUARED:
        return None

    current = ys[-1]
    hours = 0.0 if current >= threshold else (threshold - current) / slope
    if hours < 0 or hours > MAX_HORIZON_HOURS:
        return None
    predicted_at = ordered[-1].observed_at + timedelta(hours=hours)
    confidence = "high" if r_squared >= 0.85 else "medium"
    risk = "critical" if hours <= 6 else "warning" if hours <= 24 else "watch"
    return ResourceForecast(
        current_value=current,
        threshold=threshold,
        slope_per_hour=slope,
        hours_to_threshold=hours,
        predicted_at=predicted_at,
        r_squared=r_squared,
        confidence=confidence,
        risk=risk,
        sample_count=len(points),
        backtest_error=backtest_one_step(ordered),
        provider=active_provider.active,
        fallback_reason=active_provider.fallback_reason,
    )


def backtest_one_step(points: list[ForecastPoint]) -> float | None:
    """Return absolute one-step error using all but the final point for training."""
    if len(points) < MIN_FORECAST_SAMPLES + 1:
        return None
    ordered = sorted(points, key=lambda point: point.observed_at)
    training = ordered[:-1]
    origin = training[0].observed_at
    xs = [(point.observed_at - origin).total_seconds() / 3600.0 for point in training]
    ys = [point.value for point in training]
    fit = _fit_cpu(xs, ys)
    if fit is None:
        return None
    target_x = (ordered[-1].observed_at - origin).total_seconds() / 3600.0
    return abs(ordered[-1].value - (fit.intercept + fit.slope * target_x))
