from __future__ import annotations

import unittest

from rtmonitor.anomaly import robust_anomaly_score


class RobustAnomalyScoreTests(unittest.TestCase):
    def test_requires_a_minimum_baseline(self) -> None:
        self.assertIsNone(robust_anomaly_score(90.0, [20.0, 21.0, 22.0]))

    def test_ignores_normal_variation(self) -> None:
        self.assertIsNone(robust_anomaly_score(22.0, [20.0, 21.0, 22.0, 23.0, 24.0]))

    def test_flags_and_explains_a_large_deviation(self) -> None:
        result = robust_anomaly_score(90.0, [20.0, 21.0, 22.0, 23.0, 24.0])

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.baseline, 22.0)
        self.assertEqual(result.dispersion, 1.0)
        self.assertEqual(result.severity, "critical")
        self.assertGreater(result.score, 7.0)

    def test_constant_baseline_handles_change_without_dividing_by_zero(self) -> None:
        result = robust_anomaly_score(21.0, [20.0] * 5)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.score, 7.0)
        self.assertEqual(result.severity, "critical")


if __name__ == "__main__":
    unittest.main()
