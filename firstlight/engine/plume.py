"""Fire plume contribution model.

For each detected stubble fire, compute:
  - alignment: how directly the wind carries smoke school-ward (0..1)
  - reach: exponential distance decay from the source
  - intensity: fire radiative power (FRP) as a dilution-calibrated scalar

Aggregated into a single plume_score that the rules use as "what changed
overnight". This is an attribution model, deliberately transparent: the
input columns (FRP, wind, distance) stay visible in evidence.
"""

from __future__ import annotations

from math import exp, log

from ..domain import School, StubbleFire, Wind
from .geometry import (
    angular_diff_deg,
    haversine_km,
    initial_bearing_deg,
    is_fire_upwind,
    wind_toward_deg,
)

DECAY_DISTANCE_KM = 250.0  # plume concentration drops 1/e per this distance
PLUME_CAP = 3.0  # normalized cap so a heavy night reads as 3.0
FIRE_REACH_KM = 500.0
ALIGNMENT_SIGMA_DEG = 60.0


def _concentration(frp: float, distance_km: float) -> float:
    if distance_km <= 0:
        return log(1.0 + frp)
    return log(1.0 + frp) * exp(-distance_km / DECAY_DISTANCE_KM)


def _alignment(bearing_fire_to_school: float, wind: Wind) -> float:
    toward = wind_toward_deg(wind.direction_deg)
    diff = angular_diff_deg(bearing_fire_to_school, toward)
    return max(0.0, 1.0 - diff / ALIGNMENT_SIGMA_DEG)


def score_fires(fires: tuple[StubbleFire, ...], wind: Wind, school: School) -> dict:
    """Return raw contribution, upwind count, and per-fire detail."""
    contributions: list[dict] = []
    raw = 0.0
    upwind = 0
    for fire in fires:
        if fire.status != "active":
            continue
        distance = haversine_km(fire.lat, fire.lon, school.lat, school.lon)
        if distance > FIRE_REACH_KM:
            continue
        bearing = initial_bearing_deg(fire.lat, fire.lon, school.lat, school.lon)
        align = _alignment(bearing, wind)
        conc = _concentration(fire.frp, distance)
        weighted = conc * align
        if align > 0.2:  # meaningful transport alignment
            upwind += 1
        raw += weighted
        contributions.append(
            {
                "fire": fire.id,
                "district": fire.district,
                "distanceKm": round(distance, 1),
                "alignment": round(align, 2),
                "concentration": round(conc, 3),
                "weighted": round(weighted, 3),
            }
        )
    score = min(raw, PLUME_CAP)
    contributions.sort(key=lambda c: c["weighted"], reverse=True)
    return {
        "plume_score": score,
        "fires_upwind": upwind,
        "fires_in_reach": len(contributions),
        "contributions": contributions,
    }


def upwind_fire_ids(fires: tuple[StubbleFire, ...], wind: Wind, school: School) -> list[str]:
    return [
        f.id
        for f in fires
        if f.status == "active"
        and haversine_km(f.lat, f.lon, school.lat, school.lon) <= FIRE_REACH_KM
        and is_fire_upwind(f.lat, f.lon, school.lat, school.lon, wind.direction_deg)
    ]
