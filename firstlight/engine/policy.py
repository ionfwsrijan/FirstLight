"""The FirstLight policy catalog.

A named set of rules that map one morning's features to a school-day level.
Rules are ordered by severity; the first match wins (see dsl.evaluate).
Every rule carries a human detail line so the narrator can quote it verbatim.

Thresholds intentionally mirror published health guidance:
  - AQI >= 401 (Severe)  -> CLOSED
  - AQI >= 301 (Very Poor) + active plume -> CLOSED
  - AQI >= 201 (Poor)    -> PROTECTED
  - Plume + rising trend on a sensitive school -> PROTECTED at lower AQI

Sources (pinned in docs/LEARNINGS.md):
  - CPCB National Air Quality Index breakpoints (Poor >= 201, Very Poor >= 301,
    Severe >= 401): CPCB, "National Air Quality Index" (2014), aqi.pdf.
  - CAQM GRAP stages (I >= 201, II >= 301, III >= 401, IV >= 450): Commission
    for Air Quality Management in NCR, Graded Response Action Plan.
"""

from __future__ import annotations

from ..domain import Level
from ..dsl import Rule


def catalog() -> tuple[Rule, ...]:
    rules = (
        Rule(
            id="R-CLOSE-401",
            title="Severe AQI — close",
            detail="AQI >= 401 (Severe band) → CLOSED.",
            priority=10,
            predicate=lambda f: f["aqi_eff"] >= 401,
            level=Level.CLOSED,
            actions=("Declare online day", "No in-person below grade 9", "Re-evaluate at 12:00"),
        ),
        Rule(
            id="R-CLOSE-GRAP4",
            title="GRAP Stage IV — close",
            detail="AQI >= 450 invokes GRAP Stage IV → CLOSED.",
            priority=11,
            predicate=lambda f: f["grap"] >= 4,
            level=Level.CLOSED,
            actions=("Declare online day", "Re-evaluate at 12:00", "Notify ward office"),
        ),
        Rule(
            id="R-CLOSE-VP-PLUME",
            title="Very Poor + active plume — close",
            detail="AQI >= 301 and active stubble plume → CLOSED.",
            priority=12,
            predicate=lambda f: f["aqi_eff"] >= 301 and f["plume"] >= 1.0,
            level=Level.CLOSED,
            actions=("Declare online day", "Cancel outdoor PE", "Notify parents by 7:00"),
        ),
        Rule(
            id="R-PROTECT-201",
            title="Poor AQI — protect",
            detail="AQI >= 201 (Poor) → PROTECTED.",
            priority=20,
            predicate=lambda f: f["aqi_eff"] >= 201,
            level=Level.PROTECTED,
            actions=("Cancel outdoor PE", "Keep windows closed", "Masks for sensitive", "Notify parents by 7:00"),
        ),
        Rule(
            id="R-PROTECT-SENSITIVE-RISE",
            title="Sensitive + rising + plume — protect",
            detail="Sensitive school, rising trend and active plume → PROTECTED.",
            priority=21,
            predicate=lambda f: f["sensitivity"] and f["trend"] == "rising" and f["plume"] >= 0.4,
            level=Level.PROTECTED,
            actions=("Keep windows closed", "Indoor lunch", "Masks for sensitive", "Notify parents by 7:00"),
        ),
        Rule(
            id="R-PROTECT-VP-NOPLUME",
            title="Very Poor but calm — protect",
            detail="AQI 301-400 without plume → PROTECTED.",
            priority=30,
            predicate=lambda f: f["aqi_eff"] >= 301 and f["plume"] < 1.0,
            level=Level.PROTECTED,
            actions=("Cancel outdoor PE", "Keep windows closed", "Masks for sensitive", "Notify parents by 7:00"),
        ),
        Rule(
            id="R-GREEN",
            title="Clear morning — open",
            detail="No risk rule fired → GREEN.",
            priority=100,
            predicate=lambda f: True,
            level=Level.GREEN,
            actions=("Open normally", "Standard ventilation", "Outdoor break"),
        ),
    )
    return rules
