import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from firstlight import bands


class TestBandEdges(unittest.TestCase):
    def test_good(self):
        self.assertEqual(bands.score(0)["band_label"], "Good")
        self.assertEqual(bands.score(50)["band_label"], "Good")

    def test_satisfactory(self):
        self.assertEqual(bands.score(51)["band_label"], "Satisfactory")
        self.assertEqual(bands.score(100)["band_label"], "Satisfactory")

    def test_moderate(self):
        self.assertEqual(bands.score(101)["band_label"], "Moderate")
        self.assertEqual(bands.score(200)["band_label"], "Moderate")

    def test_poor(self):
        self.assertEqual(bands.score(201)["band_label"], "Poor")

    def test_very_poor(self):
        self.assertEqual(bands.score(300)["band_label"], "Poor")
        self.assertEqual(bands.score(301)["band_label"], "Very Poor")

    def test_severe(self):
        self.assertEqual(bands.score(401)["band_label"], "Severe")
        self.assertEqual(bands.score(500)["band_label"], "Severe")

    def test_clamped_out_of_range(self):
        self.assertEqual(bands.score(-5)["band_label"], "Good")
        self.assertEqual(bands.score(999)[ "band_label"], "Severe")


class TestGrapStages(unittest.TestCase):
    def test_stage_zero(self):
        self.assertEqual(bands.grap_stage_for(200), 0)

    def test_stage_one(self):
        self.assertEqual(bands.grap_stage_for(201), 1)
        self.assertEqual(bands.grap_stage_for(300), 1)

    def test_stage_two(self):
        self.assertEqual(bands.grap_stage_for(301), 2)

    def test_stage_three(self):
        self.assertEqual(bands.grap_stage_for(401), 3)
        self.assertEqual(bands.grap_stage_for(449), 3)

    def test_stage_four(self):
        self.assertEqual(bands.grap_stage_for(450), 4)
        self.assertEqual(bands.grap_stage_for(500), 4)

    def test_clamped(self):
        self.assertEqual(bands.grap_stage_for(999), 4)

    def test_hex_present(self):
        for b in bands.BANDS:
            self.assertTrue(b.hex_color.startswith("#"))


if __name__ == "__main__":
    unittest.main()