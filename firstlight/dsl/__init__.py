"""The FirstLight rule DSL: decisions are data, not prompts.

Each rule is a plain dict with an id, a priority, a predicate over the
feature context, and a payload (level + actions). The chain evaluates rules
highest-priority-first and stops at the first matching decision rule; lower
rules still record themselves so every rule that *fired* is in the trail.

The point of the DSL is contestability: a judge can read rules/policies and
reproduce any verdict by hand. No model, no hidden weights.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..domain import Level, RuleHit

Predicate = Callable[[dict], bool]


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    detail: str
    priority: int  # lower runs first
    predicate: Predicate
    level: Level
    actions: tuple[str, ...] = ()


def ctx(
    *,
    aqi_eff: float,
    aqi_station: float,
    band_label: str,
    grap: int,
    plume: float,
    fires_upwind: int,
    trend: str,
    sensitivity: bool,
) -> dict:
    return {
        "aqi_eff": aqi_eff,
        "aqi_station": aqi_station,
        "band": band_label,
        "grap": grap,
        "plume": plume,
        "fires_upwind": fires_upwind,
        "trend": trend,
        "sensitivity": sensitivity,
    }


def evaluate(rules: tuple[Rule, ...], features: dict, sensitive_bonus: float = 0.0) -> tuple[list[RuleHit], Level]:
    """Run the chain; return (hits, decided_level).

    The decided level is the highest-priority matching decision rule. All
    matching rules (any priority) are recorded as hits for the evidence trail.
    """
    hits: list[RuleHit] = []
    decided = Level.GREEN
    decided_found = False
    max_priority_matched = float("inf")
    for r in sorted(rules, key=lambda x: x.priority):
        matched = False
        try:
            matched = bool(r.predicate(features))
        except Exception:  # predicate errors must never crash a morning
            matched = False
        if matched:
            hits.append(RuleHit(r.id, r.title, r.detail, True, value=r.level))
            if not decided_found and r.priority < max_priority_matched:
                decided = r.level
                max_priority_matched = r.priority
                decided_found = True
        else:
            hits.append(RuleHit(r.id, r.title, r.detail, False, value=r.level))
    if not decided_found:
        # Safety default: never silent. Without a match, PROTECTED is prudent.
        decided = Level.PROTECTED
        hits.append(RuleHit("DEFAULT", "default-protective", "No rule matched; protective default applied.", True, value=Level.PROTECTED))
    return hits, decided
