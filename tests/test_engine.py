import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from firstlight.domain import Level, MorningInputs, School, Station, StubbleFire, Wind
from firstlight.engine import decide_school
from firstlight.engine.policy import catalog
from firstlight.dsl import evaluate, ctx


def _inputs(
    aqi: float,
    *,
    sensitive: bool = False,
    fires: int = 0,
    frp: float = 30.0,
    trend: list[float] | None = None,
) -> MorningInputs:
    school = School("test", "Test School", "Ward", 28.61, 77.21, 100, sensitive)
    station = Station("st", "Station", 28.61, 77.21, int(aqi), "PM2.5", "x")
    wind = Wind(310.0, 16.0, "x")
    fire_rows = tuple(
        StubbleFire(f"f{i}", 30.9, 75.85, f"D{i}", "Punjab", frp, "x", "active")
        for i in range(fires)
    )
    return MorningInputs("2026-10-08", (station,), (school,), fire_rows, wind, {"test": trend or [110, 115, 120, 125, 130]})


class TestEngineCore(unittest.TestCase):
    def test_green_low_aqi(self):
        d = decide_school(_inputs(150), _inputs(150).schools[0])
        self.assertEqual(d.level, Level.GREEN)

    def test_protected_at_201(self):
        d = decide_school(_inputs(201), _inputs(201).schools[0])
        self.assertEqual(d.level, Level.PROTECTED)

    def test_closed_at_401(self):
        d = decide_school(_inputs(401), _inputs(401).schools[0])
        self.assertEqual(d.level, Level.CLOSED)

    def test_closed_vp_plus_plume(self):
        d = decide_school(_inputs(340, fires=4), _inputs(340, fires=4).schools[0])
        self.assertEqual(d.level, Level.CLOSED)

    def test_protected_vp_no_plume(self):
        d = decide_school(_inputs(340, fires=0), _inputs(340, fires=0).schools[0])
        self.assertEqual(d.level, Level.PROTECTED)

    def test_sensitive_bonus_crosses_threshold(self):
        # 190 + 15 sensitive = 205 -> crosses 201, should PROTECT
        base = _inputs(190, sensitive=True)
        d = decide_school(base, base.schools[0])
        self.assertEqual(d.level, Level.PROTECTED)
        self.assertGreater(d.aqi_effective, 200)

    def test_non_sensitive_same_aqi_green(self):
        base = _inputs(190, sensitive=False)
        d = decide_school(base, base.schools[0])
        self.assertEqual(d.level, Level.GREEN)

    def test_sensitive_rising_plume_protects_low_aqi(self):
        # 180 AQI, sensitive, RISING, some plume -> PROTECTED (R-PROTECT-SENSITIVE-RISE)
        inputs = _inputs(180, sensitive=True, fires=3, trend=[100, 110, 120, 130, 190])
        d = decide_school(inputs, inputs.schools[0])
        self.assertEqual(d.level, Level.PROTECTED)

    def test_evidence_trail_present(self):
        inputs = _inputs(340, fires=4)
        d = decide_school(inputs, inputs.schools[0])
        reasons = [r for r in d.reasons if r.applied]
        self.assertTrue(reasons)
        features = d.evidence["features"]
        self.assertIn("aqi_eff", features)
        self.assertIn("plume", features)
        self.assertIn("R-CLOSE-VP-PLUME", [r.rule_id for r in reasons])

    def test_deterministic(self):
        a = decide_school(_inputs(340, fires=4), _inputs(340, fires=4).schools[0])
        b = decide_school(_inputs(340, fires=4), _inputs(340, fires=4).schools[0])
        self.assertEqual(a.to_dict(), b.to_dict())

    def test_actions_are_present(self):
        inputs = _inputs(340, fires=4)
        d = decide_school(inputs, inputs.schools[0])
        self.assertTrue(d.actions)


class TestDslCore(unittest.TestCase):
    def test_rules_are_data(self):
        rules = catalog()
        self.assertTrue(rules)
        self.assertTrue(all(r.id.startswith("R-") for r in rules))

    def test_first_match_wins(self):
        rules = catalog()
        features = ctx(aqi_eff=402.0, aqi_station=400.0, band_label="Severe", grap=3, plume=2.0, fires_upwind=5, trend="rising", sensitivity=False)
        _, level = evaluate(rules, features)
        self.assertEqual(level, Level.CLOSED)

    def test_green_default_fires(self):
        rules = catalog()
        features = ctx(aqi_eff=120.0, aqi_station=120.0, band_label="Moderate", grap=0, plume=0.0, fires_upwind=0, trend="stable", sensitivity=False)
        _, level = evaluate(rules, features)
        self.assertEqual(level, Level.GREEN)


if __name__ == "__main__":
    unittest.main()