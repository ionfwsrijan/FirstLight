import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import firstlight.pipeline.air as air  # noqa: E402
from firstlight.pipeline import effective_inputs_live, source_status  # noqa: E402
from firstlight.pipeline.provenance import live_fields  # noqa: E402
from firstlight.pipeline.scenario import STATIONS  # noqa: E402
from firstlight.storage import MetaRepo, connect  # noqa: E402

SAMPLE = {"current": {"time": "2026-10-10T12:00", "pm2_5": 58.7, "pm10": 194.2}}


class _Resp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _opener(payload):
    return lambda url, timeout=0: _Resp(json.dumps(payload).encode())


class TestCpcbAqi(unittest.TestCase):
    def test_pm25_band_boundaries(self):
        for pm25, expected in [(0, 0), (30, 50), (60, 100), (90, 200), (120, 300), (250, 400)]:
            self.assertEqual(air.cpcb_aqi(pm25, None), expected, pm25)

    def test_pm25_interpolates_within_band(self):
        self.assertEqual(air.cpcb_aqi(58.7, None), 98)

    def test_uses_max_of_sub_indices(self):
        self.assertEqual(air.cpcb_aqi(58.7, 194.2), 163)
        self.assertEqual(air.cpcb_aqi(200, 10), air.cpcb_aqi(200, None))

    def test_clamps_above_ceiling(self):
        self.assertEqual(air.cpcb_aqi(9999, None), 500)

    def test_requires_at_least_one_pollutant(self):
        with self.assertRaises(ValueError):
            air.cpcb_aqi(None, None)


class TestParseOpenMeteo(unittest.TestCase):
    def test_parse_matches_direct_computation(self):
        self.assertEqual(air.parse_openmeteo(SAMPLE), air.cpcb_aqi(58.7, 194.2))

    def test_missing_current_raises(self):
        with self.assertRaises(ValueError):
            air.parse_openmeteo({})


class TestFetchLiveStations(unittest.TestCase):
    def test_returns_aqi_per_station(self):
        readings = air.fetch_live_stations(STATIONS[:2], opener=_opener(SAMPLE))
        self.assertEqual(set(readings), {STATIONS[0].id, STATIONS[1].id})
        self.assertTrue(all(isinstance(v, int) for v in readings.values()))

    def test_skips_failing_station_but_keeps_good_ones(self):
        good = _opener(SAMPLE)
        calls = {"n": 0}

        def flaky(url, timeout=0):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("boom")
            return good(url, timeout)

        readings = air.fetch_live_stations(STATIONS[:2], opener=flaky)
        self.assertEqual(list(readings), [STATIONS[1].id])

    def test_all_failing_raises(self):
        def dead(url, timeout=0):
            raise OSError("no route")

        with self.assertRaises(RuntimeError):
            air.fetch_live_stations(STATIONS[:2], opener=dead)


class TestRefreshAir(unittest.TestCase):
    def setUp(self):
        self.conn = connect(Path(tempfile.mkdtemp()) / "air-test.db")

    def tearDown(self):
        self.conn.close()

    @mock.patch.object(air, "fetch_live_stations")
    def test_refresh_swaps_stations_and_records_provenance(self, fetch):
        fetch.return_value = {s.id: 100 + i for i, s in enumerate(STATIONS)}
        status = air.refresh_air(self.conn)
        self.assertEqual(status["source"], "open-meteo-live")
        self.assertFalse(status["fallback"])
        self.assertEqual(status["count"], len(STATIONS))
        self.assertIsNotNone(MetaRepo(self.conn).get(air.AIR_SOURCE_KEY))

        inputs, prov = effective_inputs_live(self.conn)
        self.assertEqual(prov["stations"]["source"], "open-meteo-live")
        self.assertNotEqual(inputs.stations[0].aqi, STATIONS[0].aqi)

    @mock.patch.object(air, "fetch_live_stations")
    def test_failed_refresh_falls_back_frozen_visibly(self, fetch):
        fetch.side_effect = RuntimeError("air-quality upstream unreachable")
        status = air.refresh_air(self.conn)
        self.assertEqual(status["source"], "frozen")
        self.assertTrue(status["fallback"])
        self.assertIn("unreachable", status["error"])

        inputs, prov = effective_inputs_live(self.conn)
        self.assertEqual(inputs.stations[0].aqi, STATIONS[0].aqi)

    @mock.patch.object(air, "fetch_live_stations")
    def test_backpressure_throttles_immediate_second_refresh(self, fetch):
        fetch.return_value = {STATIONS[0].id: 50}
        first = air.refresh_air(self.conn)
        second = air.refresh_air(self.conn)
        self.assertFalse(first["throttled"])
        self.assertTrue(second["throttled"])
        self.assertEqual(fetch.call_count, 1)

    def test_effective_stations_frozen_without_refresh(self):
        inputs, prov = effective_inputs_live(self.conn)
        self.assertEqual(prov["stations"]["source"], "frozen")
        self.assertEqual(inputs.stations, STATIONS)


class TestSourceStatus(unittest.TestCase):
    def setUp(self):
        self.conn = connect(Path(tempfile.mkdtemp()) / "prov-test.db")

    def tearDown(self):
        self.conn.close()

    def test_every_field_is_labelled(self):
        status = source_status(self.conn)
        for name in ("stations", "fires", "wind", "history"):
            self.assertIn(name, status)
            self.assertIn("live", status[name])
            self.assertIn("provider", status[name])
        self.assertFalse(status["wind"]["live"])
        self.assertFalse(status["history"]["live"])
        self.assertFalse(status["stations"]["live"])
        self.assertEqual(live_fields(status), [])

    @mock.patch.object(air, "fetch_live_stations")
    def test_live_station_flips_field_after_refresh(self, fetch):
        fetch.return_value = {s.id: 150 for s in STATIONS}
        air.refresh_air(self.conn)
        status = source_status(self.conn)
        self.assertTrue(status["stations"]["live"])
        self.assertEqual(live_fields(status), ["stations"])


if __name__ == "__main__":
    unittest.main()
