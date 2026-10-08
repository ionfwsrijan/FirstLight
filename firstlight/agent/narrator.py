"""Narrator: the AI voice that never invents, only narrates the Decision.

Every sentence is assembled from the Decision object's own fields and the
RuleHit details that already fired. There is no prompt, no generation, no
free text — this is what makes the 6 AM call *evidence-first*.
"""

from __future__ import annotations

from ..domain import Decision, RuleHit, School

LEVEL_LINE = {
    "GREEN": "Today is GREEN — school opens as usual.",
    "PROTECTED": "Today is PROTECTED — school is open with protective measures.",
    "CLOSED": "Today is CLOSED — classes move online.",
}


def narrate(school: School, decision: Decision) -> str:
    reasons = [h for h in decision.reasons if h.applied]
    lines = [
        f"{school.name}, {school.ward}: {LEVEL_LINE[decision.level.name_short]}",
        f"Effective AQI {decision.aqi_effective:.0f} in the '{decision.band_label}' band; GRAP Stage {decision.grap_stage}.",
    ]
    if decision.fires_upwind:
        lines.append(
            f"Plume score {decision.plume_score:.2f} from {decision.fires_upwind} upwind stubble fire(s)."
        )
    if decision.trend != "stable":
        lines.append(f"Trend is {decision.trend} ({decision.evidence['trend']['delta']:+.0f} vs baseline).")
    lines.append("Why: " + "; ".join(f"{r.rule_id}: {r.detail}" for r in reasons))
    return " ".join(lines)


def short(school: School, decision: Decision) -> str:
    return (
        f"{school.name}: {decision.level.name_short} "
        f"(AQI {decision.aqi_effective:.0f} {decision.band_label}). "
        f"Rule {'; '.join(r.rule_id for r in decision.reasons if r.applied)}."
    )


def change_summary(decision: Decision) -> str:
    ev = decision.evidence
    plume = ev["plume"]
    return (
        f"Overnight: {plume['upwindFires']} stubble fire(s) upwind, "
        f"plume {plume['score']:.2f}; AQI {ev['trend']['delta']:+.0f} vs the 7-morning baseline "
        f"({ev['trend']['baseline']:.0f}). Trend {decision.trend}."
    )