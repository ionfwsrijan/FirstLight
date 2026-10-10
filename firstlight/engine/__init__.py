"""Engine facade: turn one morning's inputs into every school's Decision.

Pure composition — no IO, no clocks, no randomness. This is the surface the
pipeline, the API, and the narrator all call.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..domain import Decision, Level, MorningInputs, RuleHit, School
from ..dsl import ctx, evaluate
from . import bands
from .interpolation import interpolate_aqi
from .plume import score_fires
from .policy import catalog
from .trend import analyze

SENSITIVE_BONUS = 15.0


def decide_school(
    inputs: MorningInputs,
    school: School,
    sensitive_bonus: float = SENSITIVE_BONUS,
) -> Decision:
    assert school.id in inputs.history_aqi, f"missing history for {school.id}"

    station_aqi = interpolate_aqi(inputs.stations, school)
    aqi_effective = station_aqi + (sensitive_bonus if school.has_sensitive_group else 0.0)

    band = bands.band_for(int(aqi_effective))
    grap = bands.grap_stage_for(int(aqi_effective))

    plume = score_fires(inputs.fires, inputs.wind, school)
    trend = analyze(aqi_effective, inputs.history_aqi[school.id])

    features = ctx(
        aqi_eff=aqi_effective,
        aqi_station=round(station_aqi, 1),
        band_label=band.label,
        grap=grap,
        plume=plume["plume_score"],
        fires_upwind=plume["fires_upwind"],
        trend=trend["trend"],
        sensitivity=school.has_sensitive_group,
    )

    hits, level = evaluate(catalog(), features)

    # Actions come only from the rules that decided THIS level; otherwise a
    # CLOSED school would inherit "Open normally" from the green baseline.
    aligned_rules = [rule for rule in catalog() if _rule_fired(rule.id, hits) and rule.level == level]
    if not aligned_rules:
        aligned_rules = [rule for rule in catalog() if rule.level == level]
    actions = tuple(
        sorted(
            {
                action
                for rule in aligned_rules
                for action in rule.actions
            }
        )
    )

    evidence = {
        "stationAqi": round(station_aqi, 1),
        "sensitiveBonusApplied": school.has_sensitive_group,
        "plume": {
            "score": round(plume["plume_score"], 3),
            "upwindFires": plume["fires_upwind"],
            "firesInReach": plume["fires_in_reach"],
        },
        "trend": trend,
        "features": {k: v for k, v in features.items()},
    }

    return Decision(
        school_id=school.id,
        date=inputs.date,
        level=level,
        aqi_effective=aqi_effective,
        band_label=band.label,
        band_hex=band.hex_color,
        grap_stage=grap,
        fires_upwind=plume["fires_upwind"],
        plume_score=plume["plume_score"],
        trend=trend["trend"],
        reasons=tuple(hits),
        actions=actions,
        evidence=evidence,
    )


def _rule_fired(rule_id: str, hits: Sequence[RuleHit]) -> bool:
    return any(h.rule_id == rule_id and h.applied for h in hits)


def decide_all(inputs: MorningInputs) -> list[Decision]:
    return [decide_school(inputs, school) for school in inputs.schools]


__all__ = ["decide_school", "decide_all", "Level", "Decision"]
