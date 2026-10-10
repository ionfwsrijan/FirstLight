"""Live fire source: NASA FIRMS public 24h CSV, with a frozen-scenario fallback.

The morning's stations, schools, wind and history stay frozen (the seeded
scenario, so a demo is reproducible). Stubble fires are the one input that
genuinely changes day to day, so they are the one allowed to be live —
visibly: provenance (source, fetch time, fallback state) is recorded in the
`meta` table and surfaced through `/api/health`, `/api/morning/inputs` and
the console's source chip. Refresh is explicit (POST /api/sources/refresh);
nothing in the engine ever touches the network.
"""

from __future__ import annotations

import csv
import hashlib
import io
import urllib.request
from dataclasses import asdict
from datetime import UTC, datetime

from ..domain import MorningInputs, StubbleFire
from ..storage import MetaRepo
from .scenario import DATE, FIRES, HISTORY, SCHOOLS, STATIONS, WIND, morning_inputs

# key-free NASA FIRMS 24h global CSVs (verified 2026-10-08, HTTP 206)
FIRMS_URLS = (
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Global_24h.csv",
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_Global_24h.csv",
)

# Punjab / Haryana / Delhi NCR box (lat_min, lon_min, lat_max, lon_max)
BBOX = (26.5, 71.5, 33.0, 78.5)
MAX_FIRES = 80
SOURCE_KEY = "fire_source"

FALLBACK_STATUS = {
    "source": "frozen",
    "label": "Frozen scenario snapshot",
    "fetchedAt": None,
    "count": len(FIRES),
    "fallback": False,
    "error": None,
}


def _label(lat: float, lon: float) -> str:
    return f"{abs(lat):.1f}{'N' if lat >= 0 else 'S'} {abs(lon):.1f}{'E' if lon >= 0 else 'W'}"


def parse_firms_csv(text: str) -> list[StubbleFire]:
    """Pure CSV -> fires (bbox-filtered). Works on both VIIRS and MODIS headers."""
    fires: list[StubbleFire] = []
    seen: set[str] = set()
    for row in csv.DictReader(io.StringIO(text)):
        try:
            lat = float(row.get("latitude") or "")
            lon = float(row.get("longitude") or "")
        except ValueError:
            continue
        if not (BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]):
            continue
        date = (row.get("acq_date") or "").strip()
        hhmm = (row.get("acq_time") or "").strip().zfill(4)[-4:]
        if not date or len(hhmm) != 4 or not hhmm.isdigit():
            continue
        try:
            frp = float(row.get("frp") or 0.0)
        except ValueError:
            frp = 0.0
        fid = "live-" + hashlib.sha1(f"{lat:.5f},{lon:.5f},{date}{hhmm}".encode()).hexdigest()[:10]
        if fid in seen:
            continue
        seen.add(fid)
        fires.append(
            StubbleFire(
                id=fid,
                lat=round(lat, 5),
                lon=round(lon, 5),
                district=_label(lat, lon),
                state="",
                frp=round(frp, 1),
                detected_utc=f"{date}T{hhmm[:2]}:{hhmm[2:]}:00Z",
                status="active",
            )
        )
    fires.sort(key=lambda f: f.frp, reverse=True)
    return fires[:MAX_FIRES]


def fetch_live_fires(timeout: float = 8.0) -> list[StubbleFire]:
    """VIIRS first, MODIS fallback. Raises RuntimeError when nothing usable."""
    errors: list[str] = []
    for url in FIRMS_URLS:
        name = url.rsplit("/", 1)[-1]
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001 - any network failure falls back
            errors.append(f"{name}: {exc}")
            continue
        fires = parse_firms_csv(text)
        if fires:
            return fires
        errors.append(f"{name}: no rows inside the Punjab-Haryana box")
    raise RuntimeError("; ".join(errors) or "FIRMS unreachable")


def _public(payload: dict | None) -> dict:
    status = dict(FALLBACK_STATUS)
    if payload:
        status.update({k: payload.get(k, status.get(k)) for k in status})
        status["count"] = len(payload.get("fires") or []) or status["count"]
    return status


def read_status(conn) -> dict:
    """Provenance for the UI (without the raw fire payloads)."""
    return _public(MetaRepo(conn).get(SOURCE_KEY))  # type: ignore[arg-type]


def effective_inputs(conn) -> tuple[MorningInputs, dict]:
    """Frozen scenario, except fires swap to the last live refresh when present."""
    payload = MetaRepo(conn).get(SOURCE_KEY)
    if isinstance(payload, dict) and payload.get("fires"):
        fires = tuple(StubbleFire(**f) for f in payload["fires"])
        inputs = MorningInputs(DATE, STATIONS, SCHOOLS, fires, WIND, HISTORY)
        return inputs, _public(payload)
    status = dict(FALLBACK_STATUS)
    if isinstance(payload, dict):
        status = _public(payload)  # keeps error/fetchedAt from a failed refresh
    return morning_inputs(), status


def refresh(conn, timeout: float = 8.0) -> dict:
    """Explicit, officer-triggered fetch. Records provenance either way."""
    now = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        fires = fetch_live_fires(timeout)
        payload = {
            "source": "firms-live",
            "label": "NASA FIRMS · live 24h",
            "fetchedAt": now,
            "count": len(fires),
            "fallback": False,
            "error": None,
            "fires": [asdict(f) for f in fires],
        }
    except Exception as exc:  # noqa: BLE001 - any failure falls back, visibly
        payload = {
            "source": "frozen",
            "label": "Frozen scenario snapshot",
            "fetchedAt": now,
            "count": len(FIRES),
            "fallback": True,
            "error": str(exc),
            "fires": None,
        }
    repo = MetaRepo(conn)
    repo.set(SOURCE_KEY, payload)
    conn.commit()
    return _public(payload)
