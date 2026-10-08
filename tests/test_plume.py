import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from firstlight.engine.plume import score_fires, upwind_fire_ids
from firstlight.domain import School, StubbleFire, Wind


def _fire(fid: str, lat: float, lon: float, frp: float = 20.0, status: str = "active") -> StubbleFire:
    return StubbleFire(fid, lat, lon, f"D-{fid}", "Punjab", frp, "2026-10-08T00:00:00Z", status)


class TestPlume(unittest.TestCase):
    def setUp(self):
        self.school = School("sch", "Test", "Ward", 28.61, 77.21, 100, False)

    def test_no_scoring_without_fires(self):
        wind = Wind(310.0, 16.0, "x")
        result = score_fires((), wind, self.school)
        self.assertEqual(result["plume_score"], 0.0)
        self.assertEqual(result["fires_upwind"], 0)

    def test_nw_fire_upwind_to_delhi(self):
        # Ludhiana-ish NW of Delhi; wind from 310 blows smoke toward SE/Delhi.
        wind = Wind(310.0, 16.0, "x")
        fires = (_fire("f1", 30.90, 75.85, frp=28.0),)
        result = score_fires(fires, wind, self.school)
        self.assertEqual(result["fires_upwind"], 1)
        self.assertGreater(result["plume_score"], 0.0)

    def test_south_fire_not_upwind(self):
        wind = Wind(310.0, 16.0, "x")
        fires = (_fire("f1", 25.0, 78.0, frp=28.0),)  # far SOUTH — smoke goes the other way
        result = score_fires(fires, wind, self.school)
        self.assertEqual(result["fires_upwind"], 0)

    def test_contained_fire_ignored(self):
        wind = Wind(310.0, 16.0, "x")
        fires = (_fire("f1", 30.90, 75.85, status="contained"),)
        result = score_fires(fires, wind, self.school)
        self.assertEqual(result["plume_score"], 0.0)

    def test_closer_fire_scores_more(self):
        wind = Wind(310.0, 16.0, "x")
        near = _fire("near", 29.5, 76.5, frp=25.0)
        far = _fire("far", 31.2, 75.2, frp=25.0)
        near_score = score_fires((near,), wind, self.school)["plume_score"]
        far_score = score_fires((far,), wind, self.school)["plume_score"]
        self.assertGreater(near_score, far_score)

    def test_upwind_id_list(self):
        wind = Wind(310.0, 16.0, "x")
        fires = (
            _fire("f1", 30.90, 75.85),
            _fire("f2", 25.0, 78.0),
        )
        ids = upwind_fire_ids(fires, wind, self.school)
        self.assertIn("f1", ids)
        self.assertNotIn("f2", ids)

    def test_plume_capped(self):
        wind = Wind(30.0, 4.0, "x")
        many_hot = tuple(_fire(f"f{i}", 28.7 + i * 0.002, 77.1, frp=60.0) for i in range(20))
        result = score_fires(many_hot, wind, self.school)
        self.assertLessEqual(result["plume_score"], 3.0)


if __name__ == "__main__":
    unittest.main()