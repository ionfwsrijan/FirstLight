"""Morning trend detector: is today better or worse than the recent baseline?

Compares today's effective AQI against a trailing-window median of the same
school's prior mornings. Output is one of Trend.* plus the raw delta so the
rules can decide whether the movement itself is a health signal.
"""

from __future__ import annotations

from collections.abc import Sequence
from statistics import median

from ..domain import Trend

WINDOW = 7  # prior mornings considered
RISE_FRAC = 0.15  # 15% above baseline = RISING
FALL_FRAC = 0.15  # 15% below baseline = IMPROVING


def analyze(today_aqi: float, prior: Sequence[float]) -> dict:
    clean = [float(x) for x in prior if x is not None and x >= 0]
    baseline = median(clean[-WINDOW:]) if clean else today_aqi
    delta = today_aqi - baseline
    frac = delta / baseline if baseline else 1.0
    if frac >= RISE_FRAC:
        trend = Trend.RISING
    elif frac <= -FALL_FRAC:
        trend = Trend.IMPROVING
    else:
        trend = Trend.STABLE
    return {
        "trend": trend.value,
        "baseline": round(baseline, 1),
        "delta": round(delta, 1),
        "delta_frac": round(frac, 3),
    }
