"""Narrator: the AI voice that never invents, only narrates the Decision.

Every sentence is assembled from the Decision object's own fields and the
RuleHit details that already fired. There is no prompt, no generation, no
free text — this is what makes the 6 AM call *evidence-first*.

Only the rules that actually decide the verdict are quoted to users. Lower
rules that merely matched (e.g. a PROTECTED rule when CLOSED won) stay in the
evidence trail but are excluded from the plain-language reply, because a
parent shouldn't have to reconcile "no risk rule fired" with a shutdown.
"""

from __future__ import annotations

from ..domain import Decision, School

LEVEL_LINE = {
    "GREEN": "Today is GREEN — school opens as usual.",
    "PROTECTED": "Today is PROTECTED — school is open with protective measures.",
    "CLOSED": "Today is CLOSED — classes move online.",
}


def _where(school: School) -> str:
    """Name plus ward, without repeating a locality already inside the name."""
    ward_first = school.ward.split()[0] if school.ward else ""
    if ward_first and ward_first not in school.name:
        return f"{school.name}, {school.ward}"
    return school.name


def decided(decision: Decision) -> list:
    """The applied RuleHits that point at the final level encodable as hit.value.

    Falls back to all applied hits if none carry a matching level (defensive
    for records produced before `value` was attached to RuleHit).
    """
    achieved = decision.level.name_short
    aligned = [r for r in decision.reasons if r.applied and getattr(r.value, "name", None) == achieved]
    return aligned or [r for r in decision.reasons if r.applied]


def narrate(school: School, decision: Decision) -> str:
    lines = [
        f"{_where(school)}: {LEVEL_LINE[decision.level.name_short]}",
        f"Effective AQI {decision.aqi_effective:.0f} in the '{decision.band_label}' band; GRAP Stage {decision.grap_stage}.",
    ]
    if decision.fires_upwind:
        lines.append(
            f"Plume score {decision.plume_score:.2f} from {decision.fires_upwind} upwind stubble fire(s)."
        )
    if decision.trend != "stable":
        lines.append(f"Trend is {decision.trend} ({decision.evidence['trend']['delta']:+.0f} vs baseline).")
    lines.append("Why: " + "; ".join(f"{r.title} ({r.rule_id})" for r in decided(decision)))
    return " ".join(lines)


def short(school: School, decision: Decision) -> str:
    head = f"{school.name} is {decision.level.name_short} today — AQI {decision.aqi_effective:.0f} ({decision.band_label})."
    winners = decided(decision)
    if decision.level.name_short != "GREEN" and winners:
        head += f" Reason: {winners[0].title}."
    return head


def status_reply(school: School, decision: Decision) -> str:
    lines = [
        f"{_where(school)}: {LEVEL_LINE[decision.level.name_short]}",
        f"Effective AQI {decision.aqi_effective:.0f} ({decision.band_label}); GRAP Stage {decision.grap_stage}.",
    ]
    if decision.fires_upwind:
        lines.append(f"Plume score {decision.plume_score:.2f} from {decision.fires_upwind} upwind stubble fire(s).")
    winners = decided(decision)
    if decision.level.name_short == "GREEN":
        lines.append("No risk rule fired — nothing to change.")
    else:
        lines.append("Why: " + "; ".join(f"{r.title} ({r.rule_id})" for r in winners))
    return "\n".join(lines)


def why_reply(school: School, decision: Decision) -> str:
    lines = [f"{decision.level.name_short}."]
    winners = decided(decision)
    for r in winners:
        lines.append(f"• {r.title}: {r.detail}")
    return "\n".join(lines)


def change_reply(school: School, decision: Decision) -> str:
    plume = decision.evidence["plume"]
    trend = decision.evidence["trend"]
    return "\n".join(
        [
            "What changed overnight:",
            f"• {plume['upwindFires']} stubble fire(s) moved upwind; plume score {plume['score']:.2f}.",
            f"• AQI {decision.aqi_effective:.0f} is {trend['delta']:+.0f} vs the 7-morning baseline ({trend['baseline']:.0f}).",
            f"• Trend: {decision.trend}.",
        ]
    )


def actions_reply(school: School, decision: Decision) -> str:
    acts = list(decision.actions)
    lines = [f"For {school.name} ({decision.level.name_short}):"]
    lines.append("• " + "\n• ".join(acts) if acts else "• Open normally.")
    return "\n".join(lines)


def greet_reply(school: School, decision: Decision) -> str:
    return (
        f"Good morning. I'm FirstLight for {school.name}. Today is {decision.level.name_short}."
        " Ask 'is today safe?', 'why?', 'what changed overnight?', or say 'send the alert' to notify parents."
    )


def send_armed_reply(school: School, decision: Decision) -> str:
    return (
        f"Understood — the alert for {school.name} ({decision.level.name_short}, AQI {decision.aqi_effective:.0f}) is armed and waiting for you."
        " Nothing is sent until you reply 'yes, send it' in this same turn."
    )


def send_confirmed_reply(school: School, decision: Decision, cert: str, channel: str = "", receipt: str = "") -> str:
    reply = (
        f"Done — the alert for {school.name} is SENT: {decision.level.name_short} ({decision.band_label}, AQI {decision.aqi_effective:.0f})."
        f" Signed receipt recorded in the tamper-evident ledger:\n{cert[:42]}…"
    )
    if channel and receipt:
        reply += f"\nDelivered via {channel} → receipt {receipt}."
    return reply


def send_denied_reply(school: School, role: str) -> str:
    return (
        f"Consent is on file, but the '{role}' role cannot dispatch alerts — only a principal or officer can."
        f" Ask one of them to confirm for {school.name}, or review the decision first."
    )


def recall_reply(school: School, decision: Decision) -> str:
    return (
        f"Recall noted. An alert for {school.name} can be withdrawn — say 'withdraw the alert' to confirm the recall."
    )


def change_summary(decision: Decision) -> str:
    ev = decision.evidence
    plume = ev["plume"]
    return (
        f"Overnight: {plume['upwindFires']} stubble fire(s) upwind, "
        f"plume {plume['score']:.2f}; AQI {ev['trend']['delta']:+.0f} vs the 7-morning baseline "
        f"({ev['trend']['baseline']:.0f}). Trend {decision.trend}."
    )