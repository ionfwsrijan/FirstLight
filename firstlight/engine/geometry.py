"""Geodesic helpers: distance, bearing, and wind alignment.

Deterministic, pure math. Used by interpolation and the plume model.
"""

from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Bearing from point 1 to point 2, degrees clockwise from north."""
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def angular_diff_deg(a: float, b: float) -> float:
    """Smallest signed difference (0..180) between two bearings."""
    diff = abs((a - b + 180.0) % 360.0 - 180.0)
    return diff


def wind_toward_deg(wind_from_deg: float) -> float:
    """Wind FROM x deg means air travels TOWARD (x+180) deg."""
    return (wind_from_deg + 180.0) % 360.0


def is_from_direction(bearing_from_source_to_target: float, wind_from_deg: float, tolerance_deg: float = 30.0) -> bool:
    """Is wind blowing from source toward target?

    A fire upwind of a school sits at a bearing from the school that matches
    the wind's FROM reading (within tolerance), so smoke advects school-ward.
    """
    school_to_fire = initial_bearing_deg(0, 0, 0, 0)  # see caller; helper kept general
    del school_to_fire
    # The fire -> school bearing aligned to wind TOWARD direction is the
    # physical test; expose a named twin below for clarity.
    return angular_diff_deg(bearing_from_source_to_target, wind_toward_deg(wind_from_deg)) <= tolerance_deg


def is_fire_upwind(
    fire_lat: float,
    fire_lon: float,
    school_lat: float,
    school_lon: float,
    wind_from_deg: float,
    tolerance_deg: float = 35.0,
) -> bool:
    """True if smoke from the fire plausibly travels toward this school."""
    fire_to_school = initial_bearing_deg(fire_lat, fire_lon, school_lat, school_lon)
    toward = wind_toward_deg(wind_from_deg)
    return angular_diff_deg(fire_to_school, toward) <= tolerance_deg
