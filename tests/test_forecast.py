from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from rtmonitor import forecast as forecast_module
from rtmonitor.execution import ExecutionProvider, resolve_execution_provider
from rtmonitor.forecast import ForecastPoint, backtest_one_step, forecast_threshold


def rising_points() -> list[ForecastPoint]:
    start = datetime(2026, 7, 30, tzinfo=UTC)
    return [
        ForecastPoint(start + timedelta(hours=index), 60.0 + index * 5)
        for index in range(6)
    ]


class ForecastTests(unittest.TestCase):
    def test_forecasts_explainable_threshold_crossing(self) -> None:
        result = forecast_threshold(rising_points(), threshold=90.0)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertAlmostEqual(result.slope_per_hour, 5.0)
        self.assertAlmostEqual(result.hours_to_threshold, 1.0)
        self.assertEqual(result.risk, "critical")
        self.assertEqual(result.confidence, "high")
        self.assertEqual(result.provider, "cpu")

    def test_rejects_insufficient_declining_and_noisy_series(self) -> None:
        points = rising_points()
        self.assertIsNone(forecast_threshold(points[:5], threshold=90.0))
        self.assertIsNone(
            forecast_threshold(
                [
                    ForecastPoint(point.observed_at, 100.0 - point.value)
                    for point in points
                ],
                threshold=90.0,
            )
        )
        noisy = [
            ForecastPoint(point.observed_at, value)
            for point, value in zip(points, (50, 80, 45, 82, 48, 70), strict=True)
        ]
        self.assertIsNone(forecast_threshold(noisy, threshold=90.0))

    def test_backtest_reports_one_step_error(self) -> None:
        points = rising_points() + [
            ForecastPoint(datetime(2026, 7, 30, 6, tzinfo=UTC), 90.0)
        ]
        error = backtest_one_step(points)
        self.assertIsNotNone(error)
        assert error is not None
        self.assertAlmostEqual(error, 0.0)

    @patch("rtmonitor.execution.importlib.util.find_spec", return_value=None)
    def test_gpu_request_falls_back_to_cpu(self, _find_spec: object) -> None:
        provider = resolve_execution_provider("gpu")
        self.assertEqual(provider.active, "cpu")
        self.assertIsNotNone(provider.fallback_reason)

    @patch("rtmonitor.execution.importlib.import_module")
    @patch("rtmonitor.execution.importlib.util.find_spec", return_value=object())
    def test_auto_uses_gpu_when_provider_is_available(
        self,
        _find_spec: object,
        import_module: object,
    ) -> None:
        import_module.return_value = SimpleNamespace(  # type: ignore[attr-defined]
            cuda=SimpleNamespace(
                runtime=SimpleNamespace(getDeviceCount=lambda: 1)
            )
        )
        provider = resolve_execution_provider("auto")
        self.assertEqual(provider.active, "gpu")
        self.assertEqual(provider.accelerator, "cupy")

    def test_forecast_uses_gpu_backend_when_selected(self) -> None:
        provider = ExecutionProvider("gpu", "gpu", "cupy", None)
        with patch(
            "rtmonitor.forecast._fit_gpu",
            side_effect=forecast_module._fit_cpu,
        ) as gpu_fit:
            result = forecast_threshold(
                rising_points(),
                threshold=90.0,
                provider=provider,
            )

        self.assertIsNotNone(result)
        assert result is not None
        gpu_fit.assert_called_once()
        self.assertEqual(result.provider, "gpu")

    def test_gpu_regression_failure_falls_back_to_cpu(self) -> None:
        provider = ExecutionProvider("gpu", "gpu", "cupy", None)
        with patch(
            "rtmonitor.forecast._fit_gpu",
            side_effect=RuntimeError("device unavailable"),
        ):
            result = forecast_threshold(
                rising_points(),
                threshold=90.0,
                provider=provider,
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.provider, "cpu")
        self.assertIn("GPU regression failed", result.fallback_reason or "")


if __name__ == "__main__":
    unittest.main()
