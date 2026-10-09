import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import firstlight.pipeline.sources as sources  # noqa: E402
from firstlight.pipeline import effective_inputs, morning_inputs  # noqa: E402
from firstlight.storage import connect, MetaRepo  # noqa: E402

VIIRS_CSV = """latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,confidence,version,bright_ti5,frp,daynight
30.123,76.5,312.4,1.0,1.0,2026-10-07,0545,VNP02IMG,high,2.0,,12.3,N
28.601,77.203,335.1,1.0,1.0,2026-10-07,0610,VNP02IMG,nominal,2.0,,8.9,N
30.124,76.501,312.5,1.0,1.0,2026-10-07,0546,VNP02IMG,high,2.0,,12.4,N
25.0,78.0,300.0,1.0,1.0,2026-10-07,0700,VNP02IMG,low,2.0,,5.0,N
33.5,77.0,290.0,1.0,1.0,2026-10-07,0700,VNP02IMG,low,2.0,,5.0,N
30.0,80.0,310.0,1.0,1.0,2026-10-07,0700,VNP02IMG,low,2.0,,5.0,N
,77.0,310.0,1.0,1.0,2026-10-07,0700,VNP02IMG,low,2.0,,5.0,N
"""

MODIS_CSV = """latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,confidence,version,bright_t31,frp,daynight
29.9,75.9,322.0,1.0,1.0,2026-10-07,0815,Terra,36,6.2,,18.0,N
28.0,76.5,300.0,1.0,1.0,2026-10-07,0820,Aqua,85,6.2,,22.5,N
25.0,78.0,290.0,1.0,1.0,2026-10-07,0830,Terra,10,6.2,,5.0,N
"""


class TestFirmsParsing(unittest.TestCase):
    def test_parses_and_filters_bbox(self):
        fires = sources.parse_firms_csv(VIIRS_CSV)
        self.assertEqual(len(fires), 3)  # 3 rows inside the bbox; 3 outside + 1 malformed dropped
        ids = [f.id for f in fires]
        self.assertEqual(len(set(ids)), len(ids))
        self.assertTrue(all(f.id.startswith("live-") for f in fires))
        self.assertTrue(all(26.5 <= f.lat <= 33.0 for f in fires))
        self.assertTrue(all(71.5 <= f.lon <= 78.5 for f in fires))
        self.assertRegex(fires[0].detected_utc, r"^2026-10-07T\d{2}:\d{2}:00Z$")
        self.assertEqual(fires[0].status, "active")
        self.assertEqual(fires[0].district, "30.1N 76.5E")

    def test_sorted_by_frp(self):
        fires = sources.parse_firms_csv(VIIRS_CSV)
        frps = [f.frp for f in fires]
        self.assertEqual(frps, sorted(frps, reverse=True))

    def test_modis_numeric_confidence(self):
        fires = sources.parse_firms_csv(MODIS_CSV)
        self.assertEqual(len(fires), 2)
        self.assertEqual(fires[0].frp, 22.5)  # top frp first

    def test_decode_errors_do_not_crash(self):
        fires = sources.parse_firms_csv("latitude,longitude,frp\nnope,foo,bar\n")
        self.assertEqual(fires, [])


class TestRefreshAndProvenance(unittest.TestCase):
    def setUp(self):
        self.conn = connect(Path(tempfile.mkdtemp()) / "src-test.db")

    def tearDown(self):
        self.conn.close()

    @mock.patch.object(sources, "fetch_live_fires")
    def test_refresh_swaps_fires_into_effective_inputs(self, fetch):
        live = sources.parse_firms_csv(VIIRS_CSV)
        fetch.return_value = live
        status = sources.refresh(self.conn)
        self.assertEqual(status["source"], "firms-live")
        self.assertFalse(status["fallback"])
        self.assertEqual(status["count"], 3)

        inputs, prov = effective_inputs(self.conn)
        self.assertEqual(prov["source"], "firms-live")
        self.assertEqual(len(inputs.fires), 3)
        self.assertNotEqual(inputs.fires[0].id, morning_inputs().fires[0].id)

    @mock.patch.object(sources, "fetch_live_fires")
    def test_failed_refresh_falls_back_frozen_but_records_error(self, fetch):
        fetch.side_effect = RuntimeError("timeout talking to NASA")
        status = sources.refresh(self.conn)
        self.assertEqual(status["source"], "frozen")
        self.assertTrue(status["fallback"])
        self.assertIn("timeout", status["error"])

        inputs, prov = effective_inputs(self.conn)
        self.assertEqual(prov["source"], "frozen")
        self.assertEqual(prov["count"], len(morning_inputs().fires))
        self.assertIsNotNone(prov["error"])

    def test_status_and_meta_roundtrip(self):
        read_before = sources.read_status(self.conn)
        self.assertEqual(read_before["source"], "frozen")
        self.assertEqual(read_before["count"], len(morning_inputs().fires))
        # no refresh has happened, so no provenance row is persisted yet
        self.assertNotIn("fires", MetaRepo(self.conn).get(sources.SOURCE_KEY) or {})


if __name__ == "__main__":
    unittest.main()