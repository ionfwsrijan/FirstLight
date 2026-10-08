import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from firstlight.engine.trend import analyze
from firstlight.domain import Trend


class TestTrend(unittest.TestCase):
    def test_stable_within_fifteen_pct(self):
        result = analyze(110.0, [100, 105, 108, 112])
        self.assertEqual(result["trend"], Trend.STABLE)
        self.assertAlmostEqual(result["baseline"], 106.5, places=1)

    def test_rising(self):
        result = analyze(200.0, [100, 105, 108, 112])
        self.assertEqual(result["trend"], Trend.RISING)
        self.assertGreater(result["delta"], 40.0)

    def test_improving(self):
        result = analyze(60.0, [100, 120, 140])
        self.assertEqual(result["trend"], Trend.IMPROVING)

    def test_empty_history_uses_today(self):
        result = analyze(150.0, [])
        self.assertEqual(result["baseline"], 150.0)
        self.assertEqual(result["trend"], Trend.STABLE)

    def test_seven_day_window(self):
        prior = list(range(1, 30))
        result = analyze(100.0, prior)
        # baseline is median of last 7 prior mornings (23..29) = 26.0
        self.assertAlmostEqual(result["baseline"], 26.0, places=1)
        self.assertEqual(result["trend"], Trend.RISING)


if __name__ == "__main__":
    unittest.main()