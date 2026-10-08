import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from firstlight.data import Station, school_by_id, station_by_id, snapshot
from firstlight import engine
from firstlight.engine import SENSITIVE_BONUS


class TestSchoolLookup(unittest.TestCase):
    def test_known_school(self):
        s = school_by_id("s-avini")
        self.assertEqual(s.station_id, "st-anand-vihar")

    def test_unknown_school_raises(self):
        with self.assertRaises(KeyError):
            school_by_id("does-not-exist")


class TestEffectiveAqi(unittest.TestCase):
    def test_sensitive_bonus_applied(self):
        school = school_by_id("s-avini")  # has_sensitive_group True
        station = station_by_id("st-anand-vihar")
        self.assertEqual(engine.effective_aqi(school, station), station.aqi + SENSITIVE_BONUS)

    def test_no_bonus_for_regular_school(self):
        school = school_by_id("s-granite")  # has_sensitive_group False
        station = station_by_id("st-gurugram")
        self.assertEqual(engine.effective_aqi(school, station), float(station.aqi))


class TestDecisionLevels(unittest.TestCase):
    def test_green(self):
        school = school_by_id("s-granite")
        station = Station("x", "X", 150, "PM2.5")
        d = engine.decide(school, station, 0)
        self.assertEqual(d.level, 0)
        self.assertEqual(d.level_name, "GREEN")

    def test_amber_from_aqi(self):
        school = school_by_id("s-granite")
        station = Station("x", "X", 220, "PM2.5")
        d = engine.decide(school, station, 0)
        self.assertEqual(d.level, 1)

    def test_amber_from_fires(self):
        # Moderate AQI (190) + active fires still ambers under the fire rule.
        school = school_by_id("s-granite")
        station = Station("x", "X", 190, "PM2.5")
        d = engine.decide(school, station, 2)
        self.assertEqual(d.level, 1)

    def test_red_from_aqi(self):
        school = school_by_id("s-granite")
        station = Station("x", "X", 310, "PM2.5")
        d = engine.decide(school, station, 0)
        self.assertEqual(d.level, 2)
        self.assertEqual(d.level_name, "RED")

    def test_red_from_grap_stage(self):
        school = school_by_id("s-granite")
        station = Station("x", "X", 401, "PM2.5")
        d = engine.decide(school, station, 0)
        self.assertEqual(d.grap_stage, 3)
        self.assertEqual(d.level, 2)

    def test_red_from_sensitive_bonus(self):
        # 290 in a sensitive school crosses the red 301 line after +15 bonus.
        sensitive = school_by_id("s-avini")
        station = Station("x", "X", 290, "PM2.5")
        d = engine.decide(sensitive, station, 0)
        self.assertGreaterEqual(d.aqi, 301)
        self.assertEqual(d.level, 2)

    def test_determinism(self):
        school = school_by_id("s-pearl")
        station = station_by_id("st-noida")
        a = engine.decide(school, station, 6).to_dict()
        b = engine.decide(school, station, 6).to_dict()
        self.assertEqual(a, b)

    def test_actions_present_for_each_level(self):
        for level in (0, 1, 2):
            school = school_by_id("s-granite")
            station = Station("x", "X", {0: 50, 1: 250, 2: 400}[level], "PM2.5")
            d = engine.decide(school, station, 0)
            self.assertTrue(len(d.actions) >= 1)


class TestSnapshot(unittest.TestCase):
    def test_snapshot_shape(self):
        s = snapshot()
        self.assertEqual(len(s["schools"]), 6)
        self.assertEqual(len(s["stations"]), 6)
        self.assertEqual(len(s["fires"]), 6)
        self.assertEqual(s["date"], "2026-10-08")


if __name__ == "__main__":
    unittest.main()