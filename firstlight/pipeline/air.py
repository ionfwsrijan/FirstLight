"""Live station air: Open-Meteo air quality -> CPCB AQI, with a frozen fallback.

The morning's wind and history stay frozen so a demo is reproducible. Air is
the second input (after stubble fires) that genuinely changes day to day, so it
is allowed to be live -- visibly. We fetch live PM2.5/PM10 from the key-free
Open-Meteo air-quality API and convert it to a CPCB statutory AQI via the CPCB
PM2.5 and PM10 sub-index breakpoints (Central Pollution Control Board,
National Air Quality Index, 2014). The AQI is the maximum of the sub-indices,
exactly as CPCB defines it. If the fetch fails for any reason the frozen
snapshot is used and provenance records the fallback -- the console never shows
"live" data that is not live.

Refresh is explicit (POST /api/sources/refresh) or scheduled; the pure engine
never touches the network. A short min-interval acts as backpressure so a burst
of calls cannot hammer the upstream.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import replace
from datetime import UTC, datetime

from ..domain import MorningInputs, Station
from ..storage import MetaRepo
from .scenario import DATE, HISTORY, SCHOOLS, STATIONS, WIND

# Open-Meteo air-quality API: free, no key. See docs/LEARNINGS.md.
OPEN_METEO_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
AIR_SOURCE_KEY = "air_source"
MIN_REFRESH_SECONDS = 60  # backpressure: ignore refreshes newer than this

# CPCB sub-index breakpoints: (conc_lo, conc_hi, aqi_lo, aqi_hi), 24h average.
# Central Pollution Control Board, National Air Quality Index (2014).
PM25_BREAKPOINTS = (
    (0, 30, 0, 50),
    (31, 60, 51, 100),
    (61, 90, 101, 200),
    (91, 120, 201, 300),
    (121, 250, 301, 400),
    (251, 350, 401, 500),
)
PM10_BREAKPOINTS = (
    (0, 50, 0, 50),
    (51, 100, 51, 100),
    (101, 250, 101, 200),
    (251, 350, 201, 300),
    (351, 430, 301, 400),
    (431, 500, 401, 500),
)

FALLBACK_AIR_STATUS = {
    "source": "frozen",
    "label": "Frozen scenario snapshot",
    "fetchedAt": None,
    "count": len(STATIONS),
    "fallback": False,
    "throttled": False,
    "error": None,
}


def _sub_index(conc: float, table: tuple[tuple[int, int, int, int], ...]) -> int:
    """CPCB linear-interpolation sub-index for one pollutant (clamped 0-500)."""
    c = max(0.0, float(conc))
    for c_lo, c_hi, i_lo, i_hi in table:
        if c <= c_hi:
            cc = max(float(c_lo), min(c, float(c_hi)))
            return round((i_hi - i_lo) / (c_hi - c_lo) * (cc - c_lo) + i_lo)
    return 500


def cpcb_aqi(pm25: float | None, pm10: float | None) -> int:
    """CPCB AQI = max(sub-index PM2.5, sub-index PM10)."""
    sub_indices = []
    if pm25 is not None:
        sub_indices.append(_sub_index(pm25, PM25_BREAKPOINTS))
    if pm10 is not None:
        sub_indices.append(_sub_index(pm10, PM10_BREAKPOINTS))
    if not sub_indices:
        raise ValueError("neither pm2_5 nor pm10 present")
    return max(sub_indices)


def parse_openmeteo(payload: dict) -> int:
    cur = payload.get("current") or {}
    return cpcb_aqi(cur.get("pm2_5"), cur.get("pm10"))


def _station_url(station: Station) -> str:
    return (
        f"{OPEN_METEO_URL}?latitude={station.lat}&longitude={station.lon}"
        "&current=pm2_5,pm10&timezone=UTC"
    )


def fetch_live_stations(
    stations: tuple[Station, ...], timeout: float = 8.0, opener=urllib.request.urlopen
) -> dict[str, int]:
    """Live AQI per station id. Raises RuntimeError when nothing usable."""
    readings: dict[str, int] = {}
    errors: list[str] = []
    for station in stations:
        try:
            with opener(_station_url(station), timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            readings[station.id] = parse_openmeteo(payload)
        except Exception as exc:  # noqa: BLE001 - any failure skips the station
            errors.append(f"{station.id}: {exc}")
    if not readings:
        raise RuntimeError("; ".join(errors) or "air-quality upstream unreachable")
    return readings


def _public(payload: dict | None) -> dict:
    status = dict(FALLBACK_AIR_STATUS)
    if payload:
        status.update({k: payload.get(k, status.get(k)) for k in status})
        status["count"] = len(payload.get("stations") or []) or status["count"]
    return status


def read_air_status(conn) -> dict:
    return _public(MetaRepo(conn).get(AIR_SOURCE_KEY))  # type: ignore[arg-type]


def effective_stations(conn) -> tuple[tuple[Station, ...], dict]:
    """Frozen scenario, except station AQI swaps to the last live refresh."""
    payload = MetaRepo(conn).get(AIR_SOURCE_KEY)
    if isinstance(payload, dict) and payload.get("stations"):
        aqi_by_id = {s["id"]: s["aqi"] for s in payload["stations"]}
        stations = tuple(
            replace(s, aqi=aqi_by_id[s.id]) if s.id in aqi_by_id else s for s in STATIONS
        )
        return stations, _public(payload)
    status = dict(FALLBACK_AIR_STATUS)
    if isinstance(payload, dict):
        status = _public(payload)
    return STATIONS, status


def _age_seconds(payload: dict | None) -> float | None:
    if not isinstance(payload, dict) or not payload.get("fetchedAt"):
        return None
    try:
        fetched = datetime.fromisoformat(payload["fetchedAt"])
    except ValueError:
        return None
    return (datetime.now(UTC) - fetched).total_seconds()


def refresh_air(conn, timeout: float = 8.0, opener=urllib.request.urlopen) -> dict:
    """Explicit, officer/scheduled fetch. Records provenance either way.

    Backpressure: a request within MIN_REFRESH_SECONDS of the last one returns
    the cached result instead of calling upstream again.
    """
    repo = MetaRepo(conn)
    cached = repo.get(AIR_SOURCE_KEY)
    cached = cached if isinstance(cached, dict) else None
    age = _age_seconds(cached)
    if age is not None and age < MIN_REFRESH_SECONDS:
        status = _public(cached)
        status["throttled"] = True
        return status

    now = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        readings = fetch_live_stations(STATIONS, timeout, opener)
        payload = {
            "source": "open-meteo-live",
            "label": "Open-Meteo air quality → CPCB AQI",
            "fetchedAt": now,
            "count": len(readings),
            "fallback": False,
            "throttled": False,
            "error": None,
            "stations": [{"id": sid, "aqi": aqi} for sid, aqi in readings.items()],
        }
    except Exception as exc:  # noqa: BLE001 - any failure falls back, visibly
        payload = {
            "source": "frozen",
            "label": "Frozen scenario snapshot",
            "fetchedAt": now,
            "count": len(STATIONS),
            "fallback": True,
            "throttled": False,
            "error": str(exc),
            "stations": None,
        }
    repo.set(AIR_SOURCE_KEY, payload)
    conn.commit()
    return _public(payload)


def effective_inputs_live(conn) -> tuple[MorningInputs, dict]:
    """Morning inputs with live stations and (last) live fires when present."""
    from .sources import effective_inputs as _fire_inputs

    base, fire_status = _fire_inputs(conn)
    stations, air_status = effective_stations(conn)
    inputs = MorningInputs(DATE, stations, SCHOOLS, base.fires, WIND, HISTORY)
    return inputs, {"stations": air_status, "fires": fire_status}


__all__ = [
    "AIR_SOURCE_KEY",
    "FALLBACK_AIR_STATUS",
    "effective_inputs_live",
    "effective_stations",
    "fetch_live_stations",
    "cpcb_aqi",
    "parse_openmeteo",
    "read_air_status",
    "refresh_air",
]
