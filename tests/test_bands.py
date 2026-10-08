import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from firstlight.engine import bands


class TestBands(unittest.TestCase):
    def test_good(self):
        self.assertEqual(bands.band_for(0).label, "Good")
        self.assertEqual(bands.band_for(50).label, "Good")

    def test_satisfactory(self):
        self.assertEqual(bands.band_for(51).label, "Satisfactory")
        self.assertEqual(bands.band_for(100).label, "Satisfactory")

    def test_moderate(self):
        self.assertEqual(bands.band_for(101).label, "Moderate")
        self.assertEqual(bands.band_for(200).label, "Moderate")

    def test_poor(self):
        self.assertEqual(bands.band_for(201).label, "Poor")
        self.assertEqual(bands.band_for(300).label, "Poor")

    def test_very_poor(self):
        self.assertEqual(bands.band_for(301).label, "Very Poor")
        self.assertEqual(bands.band_for(400).label, "Very Poor")

    def test_severe(self):
        self.assertEqual(bands.band_for(401).label, "Severe")
        self.assertEqual(bands.band_for(500).label, "Severe")

    def test_clamped(self):
        self.assertEqual(bands.band_for(-3).label, "Good")
        self.assertEqual(bands.band_for(900).label, "Severe")


class TestGrap(unittest.TestCase):
    def test_no_stage_below_201(self):
        self.assertEqual(bands.grap_stage_for(200), 0)

    def test_stage_boundaries(self):
        self.assertEqual(bands.grap_stage_for(201), 1)
        self.assertEqual(bands.grap_stage_for(301), 2)
        self.assertEqual(bands.grap_stage_for(401), 3)
        self.assertEqual(bands.grap_stage_for(450), 4)
        self.assertEqual(bands.grap_stage_for(500), 4)


class TestLevels(unittest.TestCase):
    def test_severe_closes(self):
        from firstlight.domain import Level

        self.assertIs(bands.level_for(401, 0), Level.CLOSED)

    def test_very_poor_protects(self):
        from firstlight.domain import Level

        self.assertIs(bands.level_for(301, 0), Level.PROTECTED)

    def test_poor_protects(self):
        from firstlight.domain import Level

        self.assertIs(bands.level_for(201, 0), Level.PROTECTED)

    def test_moderate_green_without_fires(self):
        from firstlight.domain import Level

        self.assertIs(bands.level_for(180, 0), Level.GREEN)

    def test_fires_amplify_lower_edge(self):
        from firstlight.domain import Level

        self.assertIs(bands.level_for(260, 4), Level.PROTECTED)
        self.assertIs(bands.level_for(260, 0), Level.PROTECTED)


if __name__ == "__main__":
    unittest.main()