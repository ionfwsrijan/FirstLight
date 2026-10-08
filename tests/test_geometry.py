import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from firstlight.engine.geometry import (
    angular_diff_deg,
    haversine_km,
    initial_bearing_deg,
    is_fire_upwind,
    wind_toward_deg,
)


class TestGeometry(unittest.TestCase):
    def test_delhi_to_gurugram_distance(self):
        # Anand Vihar -> Gurugram, ~ 36 km by road; great-circle ~32-35km
        d = haversine_km(28.6462, 77.3157, 28.4595, 77.0266)
        self.assertGreater(d, 28.0)
        self.assertLess(d, 37.0)

    def test_zero_distance(self):
        self.assertAlmostEqual(haversine_km(28.6, 77.2, 28.6, 77.2), 0.0, places=3)

    def test_bearing_north(self):
        self.assertAlmostEqual(initial_bearing_deg(0, 0, 1, 0), 0.0, places=1)

    def test_bearing_east(self):
        self.assertAlmostEqual(initial_bearing_deg(0, 0, 0, 1), 90.0, places=1)

    def test_bearing_wrap(self):
        self.assertAlmostEqual(initial_bearing_deg(0, 0, 0, -1), 270.0, places=1)

    def test_angular_diff(self):
        self.assertAlmostEqual(angular_diff_deg(10, 20), 10.0)
        self.assertAlmostEqual(angular_diff_deg(350, 10), 20.0)

    def test_wind_toward(self):
        self.assertAlmostEqual(wind_toward_deg(310.0), 130.0)
        self.assertAlmostEqual(wind_toward_deg(0.0), 180.0)

    def test_fire_upwind_aligned(self):
        # Ludhiana stall (NW of Delhi); wind from 310 blows smoke toward SE/Delhi.
        self.assertTrue(is_fire_upwind(30.90, 75.85, 28.61, 77.21, 310.0))

    def test_fire_downwind_not_upwind(self):
        # Fire SE of school; wind from NW carries smoke further SE, not to school.
        self.assertFalse(is_fire_upwind(25.0, 78.0, 28.61, 77.21, 310.0))


if __name__ == "__main__":
    unittest.main()