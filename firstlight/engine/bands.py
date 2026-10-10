"""CPCB AQI bands and GRAP stages, codified from published thresholds.

Pure, deterministic lookups. Same input -> same output, always.
These tables are the rule engine; the AI only narrates what is here.

Sources (also cited in docs/LEARNINGS.md):
  - CPCB National Air Quality Index, "AQI breakpoints" (Good 0-50, Satisfactory
    51-100, Moderate 101-200, Poor 201-300, Very Poor 301-400, Severe 401-500):
    Central Pollution Control Board, "National Air Quality Index" (Oct 2014).
  - GRAP stage triggers for Delhi-NCR (I at 201, II at 301, III at 401,
    IV at 450): Commission for Air Quality Management (CAQM) Graded Response
    Action Plan. Tests in tests/test_bands.py pin these exact values.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain import Level


@dataclass(frozen=True)
class Band:
    index: int
    label: str
    short: str
    hex_color: str
    lo: int
    hi: int

    def contains(self, aqi: int) -> bool:
        return self.lo <= aqi <= self.hi

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "label": self.label,
            "short": self.short,
            "hex": self.hex_color,
            "lo": self.lo,
            "hi": self.hi,
        }


BANDS: tuple[Band, ...] = (
    Band(0, "Good", "GOOD", "#2eb872", 0, 50),
    Band(1, "Satisfactory", "SAT", "#a3c000", 51, 100),
    Band(2, "Moderate", "MOD", "#f7d800", 101, 200),
    Band(3, "Poor", "POOR", "#ea8a00", 201, 300),
    Band(4, "Very Poor", "PROTECT", "#c04a00", 301, 400),
    Band(5, "Severe", "CLOSE", "#8a1320", 401, 500),
)

# GRAP action plan stages for NCR, per CAQM staging.
_GRAP_TRIGGERS: tuple[tuple[int, int], ...] = (
    (450, 4),
    (401, 3),
    (301, 2),
    (201, 1),
)


def band_for(aqi: int) -> Band:
    aqi = max(0, min(500, int(aqi)))
    for b in BANDS:
        if b.contains(aqi):
            return b
    return BANDS[-1]


def grap_stage_for(aqi: int) -> int:
    aqi = max(0, min(500, int(aqi)))
    for threshold, stage in _GRAP_TRIGGERS:
        if aqi >= threshold:
            return stage
    return 0


def level_for(aqi: int, fires_upwind: int) -> Level:
    """Level dispatch used by the engine rule chain.

    Consistent with the GRAP/CPCB core (before school-specific modifiers):
    Severe AQI -> closed; Very Poor -> protected; fires amplify the lower edge.
    """
    stage = grap_stage_for(aqi)
    if aqi >= 401 or stage >= 3:
        return Level.CLOSED
    if aqi >= 301 or (aqi >= 250 and fires_upwind >= 3):
        return Level.PROTECTED
    if aqi >= 201:
        return Level.PROTECTED
    return Level.GREEN


def describe(aqi: int) -> dict:
    b = band_for(aqi)
    return {
        "aqi": aqi,
        "band_index": b.index,
        "band_label": b.label,
        "band_short": b.short,
        "grap_stage": grap_stage_for(aqi),
        "level": int(level_for(aqi, 0)),
    }
