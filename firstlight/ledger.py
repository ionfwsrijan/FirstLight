"""The change ledger: what happened overnight that made this morning bad.

Every morning the ledger answers the on-call question in four lines: what
changed, where the smoke came from, how much AQI moved, and whether it is
still moving. It is a feed of events, not a model — deterministic, replayable.
"""

from __future__ import annotations

from dataclasses import dataclass

from .data import FIRES, STATIONS

# Simplest defensible load: the pairing of upstream stubble fires with the
# stations whose AQI crossed the 'Very Poor' band overnight.
UPSTREAM_STATES = ("Punjab", "Haryana")
AMBER_BAND_MIN = 201


@dataclass(frozen=True)
class LedgerEntry:
    fire_id: str
    district: str
    state: str
    status: str
    time_utc: str


def _active_upstream_fires() -> tuple[LedgerEntry, ...]:
    return tuple(
        LedgerEntry(f.id, f.district, f.state, f.status, f.time_utc)
        for f in FIRES
        if f.state in UPSTREAM_STATES
    )


def _pressure_readings() -> list[dict]:
    # Stations that tip into the 'red window' band this morning.
    rows = []
    for s in STATIONS:
        if s.aqi >= AMBER_BAND_MIN:
            rows.append({"station": s.name, "aqi": s.aqi})
    return rows


def summarize() -> dict:
    fires = _active_upstream_fires()
    pressure = _pressure_readings()
    peak = max((r["aqi"] for r in pressure), default=0)
    return {
        "date": "2026-10-08",
        "what_changed": (
            f"{len(fires)} active stubble fires detected overnight across "
            "Punjab and Haryana, pushing {n} stations into the red window."
            .format(n=len(pressure))
        ),
        "fires": [e.__dict__ for e in fires],
        "pressure_stations": pressure,
        "peak_aqi": peak,
        "wind": {
            "direction": "north-westerly",
            "note": "carries crop-residue smoke into NCR by first light",
        },
        "ledger_version": "firstlight-ledger-v1@2026-10",
    }