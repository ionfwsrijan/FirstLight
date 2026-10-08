"""Pure data: the health snapshot FirstLight reasons over.

A Snapshot is a frozen read of one morning: per-station AQI, the stubble fires
detected overnight (the change ledger), and the schools that depend on one
specific station. Every table here is a plain dict/list so the whole product
is inspectable, assertable, and shareable between the rule engine, the agent,
and the UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Fixed demo morning. Deterministic by construction.
DEMO_DATE = date(2026, 10, 8)


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    aqi: int
    main_pollutant: str


@dataclass(frozen=True)
class School:
    id: str
    name: str
    ward: str
    station_id: str
    strength: int
    has_sensitive_group: bool


@dataclass(frozen=True)
class StubbleFire:
    id: str
    time_utc: str
    district: str
    state: str
    land: str
    status: str  # active / contained


# Real paired station readings (representative of a Delhi-typical bad morning).
STATIONS: tuple[Station, ...] = (
    Station("st-anand-vihar", "Anand Vihar, Delhi", 427, "PM2.5"),
    Station("st-ito", "ITO, Delhi", 289, "PM2.5"),
    Station("st-pusa", "Pusa, Delhi", 318, "PM2.5"),
    Station("st-shadipur", "Shadipur, Delhi", 356, "PM2.5"),
    Station("st-gurugram", "Gurugram, Haryana", 264, "PM2.5"),
    Station("st-noida", "Noida, UP", 301, "PM2.5"),
)

# One school per station so every demo card has a working table row.
SCHOOLS: tuple[School, ...] = (
    School("s-avini", "Ramjas P. Block, Ashok Vihar", "Ashok Vihar", "st-anand-vihar", 820, True),
    School("s-guard", "GGSSS, ITO Crossing", "ITO", "st-ito", 1210, False),
    School("s-apj", "CPM Public School, Pusa Road", "Pusa", "st-pusa", 540, True),
    School("s-spring", "Spring Meadow, Shadipur", "Shadipur", "st-shadipur", 460, True),
    School("s-granite", "Delhi Public School, Gurugram", "Sector 45", "st-gurugram", 1180, False),
    School("s-pearl", "Pearl Academy, Noida", "Sector 62", "st-noida", 690, False),
)

# The night's stubble fires upstream (Ludhiana-Sirsa axis) on the demo morning.
FIRES: tuple[StubbleFire, ...] = (
    StubbleFire("f-23-0912", "2026-10-07T21:12Z", "Ludhiana", "Punjab", "crop residue", "active"),
    StubbleFire("f-24-0005", "2026-10-07T22:05Z", "Mansa", "Punjab", "crop residue", "active"),
    StubbleFire("f-24-0141", "2026-10-07T23:41Z", "Barnala", "Punjab", "crop residue", "active"),
    StubbleFire("f-24-0312", "2026-10-08T01:12Z", "Sirsa", "Haryana", "crop residue", "active"),
    StubbleFire("f-24-0610", "2026-10-08T02:10Z", "Fatehabad", "Haryana", "crop residue", "contained"),
    StubbleFire("f-24-0833", "2026-10-08T04:33Z", "Sangrur", "Punjab", "crop residue", "active"),
)


def station_by_id(sid: str) -> Station:
    for s in STATIONS:
        if s.id == sid:
            return s
    raise KeyError(sid)


def school_by_id(sid: str) -> School:
    for s in SCHOOLS:
        if s.id == sid:
            return s
    raise KeyError(sid)


def snapshot() -> dict:
    return {
        "date": DEMO_DATE.isoformat(),
        "stations": [s.__dict__ for s in STATIONS],
        "schools": [s.__dict__ for s in SCHOOLS],
        "fires": [f.__dict__ for f in FIRES],
    }