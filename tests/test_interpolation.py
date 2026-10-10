import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from firstlight.domain import School, Station
from firstlight.engine.interpolation import interpolate_aqi, nearest_stations


def _mk(n: int, aqi: int) -> list[Station]:
    return [
        Station(f"s{i}", f"Station {i}", 28.6 + i * 0.01, 77.2, aqi + i * 10, "PM2.5", "2026-10-08T00:00:00Z")
        for i in range(n)
    ]


class TestInterpolation(unittest.TestCase):
    def setUp(self):
        self.school = School("sch", "Test", "Ward", 28.6, 77.2, 100, False)

    def test_single_nearest(self):
        stations = tuple(_mk(1, 300))
        self.assertAlmostEqual(interpolate_aqi(stations, self.school), 300.0, places=1)

    def test_nearest_winning_weight(self):
        far = Station("f", "Far", 28.62, 77.21, 200, "PM2.5", "x")
        near = Station("n", "Near", 28.601, 77.201, 400, "PM2.5", "x")
        value = interpolate_aqi((far, near), self.school)
        self.assertGreater(value, 300.0)
        self.assertLess(value, 400.0)

    def test_four_nearest_returned(self):
        stations = tuple(_mk(6, 200))
        rows = nearest_stations(stations, self.school)
        self.assertLessEqual(len(rows), 4)

    def test_unknown_no_stations_raises(self):
        far = Station("f", "Far", 30.0, 80.0, 200, "PM2.5", "x")  # > 40km away
        with self.assertRaises(ValueError):
            interpolate_aqi((far,), self.school)


if __name__ == "__main__":
    unittest.main()
