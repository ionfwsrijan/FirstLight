"""The deterministic decision engine for one school morning.

Rule-based on purpose: any judge can reproduce any verdict, because the rules
are open tables, not a model's mood. The AI layer narrates this `Decision`;
it never changes the numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import bands
from .data import School, Station

# Rule thresholds, written as one table instead of prose so tests can pin them.
# 0=Green, 1=Amber, 2=Red. Higher severity wins; tie goes to stricter.
EDGE_AQI_AMBER = 201.0
EDGE_AQI_RED = 301.0
EDGE_GRAP_RED = 3  # Stage III or stricter forces red
SENSITIVE_BONUS = 15.0  # AQI points added to schools with a sensitive group
FIRE_ACTIVE_AMBER = 1  # at least one active upstream fire tips amber->red window


@dataclass(frozen=True)
class Decision:
    school_id: str
    level: int  # 0 green, 1 amber, 2 red
    level_name: str
    aqi: float  # effective AQI after school-specific modifier
    band_label: str
    grap_stage: int
    fires_active: int
    reasons: tuple[str, ...]
    actions: tuple[str, ...]
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "schoolId": self.school_id,
            "level": self.level,
            "levelName": self.level_name,
            "aqi": self.aqi,
            "bandLabel": self.band_label,
            "grapStage": self.grap_stage,
            "firesActive": self.fires_active,
            "reasons": list(self.reasons),
            "actions": list(self.actions),
            "evidence": self.evidence,
        }


def effective_aqi(school: School, station: Station) -> float:
    aqi = float(station.aqi)
    if school.has_sensitive_group:
        aqi += SENSITIVE_BONUS
    return aqi


def decide(school: School, station: Station, active_fires: int) -> Decision:
    eff = effective_aqi(school, station)
    band = bands.band_for(int(eff))
    stage = bands.grap_stage_for(int(eff))

    level = 0
    reasons: list[str] = []
    if eff >= EDGE_AQI_RED or stage >= EDGE_GRAP_RED:
        level = 2
        reasons.append(
            f"AQI {eff:.0f} in '{band.label}' band — council threshold for full closure"
        )
        if stage >= EDGE_GRAP_RED:
            reasons.append(f"GRAP Stage {stage} formally invoked in this ward")
    elif eff >= EDGE_AQI_AMBER or (active_fires >= FIRE_ACTIVE_AMBER and eff >= 180):
        level = 1
        reasons.append(
            f"AQI {eff:.0f} in '{band.label}' band — requires protective measures"
        )
        if active_fires >= FIRE_ACTIVE_AMBER:
            reasons.append(f"{active_fires} active stubble fire(s) upstream this morning")
    else:
        reasons.append(f"AQI {eff:.0f} — a normal-morning reading for this school")

    actions = ACTIONS[level]
    level_name = LEVEL_NAMES[level]
    return Decision(
        school_id=school.id,
        level=level,
        level_name=level_name,
        aqi=round(eff, 1),
        band_label=band.label,
        grap_stage=stage,
        fires_active=active_fires,
        reasons=tuple(reasons),
        actions=tuple(actions),
        evidence={
            "station": station.id,
            "school": school.id,
            "sensitivePenaltyApplied": school.has_sensitive_group,
            "rulesetVersion": RULESET_VERSION,
        },
    )


LEVEL_NAMES = {0: "GREEN", 1: "AMBER", 2: "RED"}

ACTIONS: dict[int, list[str]] = {
    0: (
        "Open normally.",
        "Keep classrooms ventilated.",
        "Standard outdoor break.",
    ),
    1: (
        "Cancel outdoor PE and morning assembly.",
        "Keep windows closed; run air purifiers where available.",
        "N95 masks recommended for sensitive groups (asthma, cardiac).",
        "Notify parents by 7:00 via the school group.",
    ),
    2: (
        "Declare a work-from-home / online day.",
        "No in-person classes below grade 9.",
        "School gates closed; staff telework where possible.",
        "Broadcast the decision and its evidence to parents and the ward office.",
        "Re-evaluate at 12:00 against the midday AQI reading.",
    ),
}

RULESET_VERSION = "firstlight-rules-v1@2026-10"