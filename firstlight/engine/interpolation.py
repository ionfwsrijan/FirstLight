"""Inverse-Distance-Weighted AQI interpolation from stations to a school.

A school's effective AQI is the IDW blend of the four nearest stations,
distance-weighted (1/d). Falls back to the single nearest station when too
few readings exist. Deterministic and unit-testable.
"""

from __future__ import annotations

from ..domain import School, Station
from .geometry import haversine_km

NEAREST_N = 4
MAX_RADIUS_KM = 40.0


def nearest_stations(
    stations: tuple[Station, ...], school: School, n: int = NEAREST_N, max_radius_km: float = MAX_RADIUS_KM
) -> tuple[tuple[Station, float], ...]:
    """Return up to n (station, distance_km) sorted ascending within radius."""
    rows = []
    for s in stations:
        d = haversine_km(school.lat, school.lon, s.lat, s.lon)
        if d <= max_radius_km:
            rows.append((s, d))
    rows.sort(key=lambda r: r[1])
    return tuple(rows[:n])


def interpolate_aqi(stations: tuple[Station, ...], school: School) -> float:
    """IDW blend of the nearest stations. Single-station fallback at d=0."""
    rows = nearest_stations(stations, school)
    if not rows:
        raise ValueError(f"no stations within {MAX_RADIUS_KM}km of {school.id}")
    weight_sum = 0.0
    aqi_sum = 0.0
    for station, dist in rows:
        w = 1.0 / (dist + 1e-3) ** 2
        weight_sum += w
        aqi_sum += w * station.aqi
    return aqi_sum / weight_sum