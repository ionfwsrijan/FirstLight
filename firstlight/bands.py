"""CPCB AQI bands and GRAP stages, codified from published thresholds.

Everything here is a pure, deterministic lookup. Same AQI in, same band out.
No model, no randomness, no network. These tables are the rule engine that
decides; the narrative layer only narrates what the table already said.
"""

from __future__ import annotations

from dataclasses import dataclass


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


BANDS: tuple[Band, ...] = (
    Band(0, "Good", "GOOD", "#2eb872", 0, 50),
    Band(1, "Satisfactory", "SAT", "#a3c000", 51, 100),
    Band(2, "Moderate", "MOD", "#f8f800", 101, 200),
    Band(3, "Poor", "POOR", "#f06000", 201, 300),
    Band(4, "Very Poor", "VP", "#a01800", 301, 400),
    Band(5, "Severe", "SEV", "#7e0023", 401, 500),
)

GRAP_TRIGGERS: tuple[tuple[int, int], ...] = (
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
    raise ValueError(f"no band for aqi={aqi}")  # pragma: no cover


def grap_stage_for(aqi: int) -> int:
    aqi = max(0, min(500, int(aqi)))
    for threshold, stage in GRAP_TRIGGERS:
        if aqi >= threshold:
            return stage
    return 0


def score(aqi: int) -> dict:
    b = band_for(aqi)
    return {
        "aqi": aqi,
        "band_index": b.index,
        "band_label": b.label,
        "band_short": b.short,
        "hex": b.hex_color,
        "grap_stage": grap_stage_for(aqi),
    }