import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from firstlight import ledger


class TestLedger(unittest.TestCase):
    def test_summary_shape(self):
        s = ledger.summarize()
        self.assertEqual(s["date"], "2026-10-08")
        self.assertIn("fires", s)
        self.assertIn("pressure_stations", s)
        self.assertIn("peak_aqi", s)
        self.assertIn("wind", s)

    def test_fires_all_upstream(self):
        s = ledger.summarize()
        for f in s["fires"]:
            self.assertIn(f["state"], ("Punjab", "Haryana"))

    def test_active_fires_present(self):
        s = ledger.summarize()
        self.assertTrue(len(s["fires"]) >= 1)

    def test_pressure_stations_ncr(self):
        s = ledger.summarize()
        self.assertTrue(len(s["pressure_stations"]) >= 1)
        peak = max(r["aqi"] for r in s["pressure_stations"])
        self.assertEqual(peak, s["peak_aqi"])
        self.assertGreaterEqual(peak, 427)

    def test_deterministic(self):
        self.assertEqual(ledger.summarize(), ledger.summarize())


if __name__ == "__main__":
    unittest.main()