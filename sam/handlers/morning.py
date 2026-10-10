"""Ship It mirror of FIRSTLIGHT pipeline/morning.py.

Uses the frozen scenario for date 2026-10-08 (same as the local build) so the
demo and the deployed twin show identical verdicts -- unless a live source
refresh has swapped in real stations/fires (see sources.py), in which case it
uses those, exactly like the local build. The run is gated to the officer role
(mirroring the local "run:morning" capability) and every decision, alert and the
run itself is appended to the hash-chained LEDGER collection.

`schedule_handler` is the autonomous path: EventBridge fires it at 06:00 IST so
the morning runs whether or not anyone logs in. It refreshes live sources first
(when SOURCE_MODE=live) and records the trigger in the ledger.
"""

from __future__ import annotations

import os

from firstlight.agent import narrate, sign
from firstlight.engine import decide_all

try:
    from .shared import (
        append_ledger,
        cognito_role,
        effective_inputs_dyn,
        get_latest,
        notify_webhook,
        now_utc,
        principal_id,
        put_alert,
        put_decision,
        refresh_air_dyn,
        refresh_fires_dyn,
        respond,
    )
except ImportError:  # Lambda treats handlers/ as the code root (no package parent)
    from shared import (
        append_ledger,
        cognito_role,
        effective_inputs_dyn,
        get_latest,
        notify_webhook,
        now_utc,
        principal_id,
        put_alert,
        put_decision,
        refresh_air_dyn,
        refresh_fires_dyn,
        respond,
    )


def _run(who: str) -> dict:
    """Decide every school, persist to DynamoDB, alert, and ledger it."""
    inputs = effective_inputs_dyn()
    summary = {"date": inputs.date, "decisions": [], "alerts": []}
    for decision in decide_all(inputs):
        summary["decisions"].append(decision.to_dict())
        put_decision(decision.school_id, decision.to_dict())

        cert = sign(decision, "shipit-demo-key")
        append_ledger("decision", decision.school_id, {
            "date": decision.date,
            "level": decision.level.name_short,
            "aqiEffective": round(decision.aqi_effective, 1),
            "grapStage": decision.grap_stage,
            "cert": cert,
        })

        if decision.level.name_short in ("PROTECTED", "CLOSED"):
            school = next(s for s in inputs.schools if s.id == decision.school_id)
            message = narrate(school, decision)
            receipt = notify_webhook(decision.level.name_short, message)
            channel = "webhook" if receipt.startswith("hook") else "noop"
            put_alert(
                decision.school_id, decision.date, decision.level.name_short, cert,
                message, channel, receipt, who, now_utc(),
            )
            summary["alerts"].append({
                "schoolId": decision.school_id,
                "level": decision.level.name_short,
                "receipt": receipt,
                "channel": channel,
            })

    append_ledger("morning_run", inputs.date, {
        "asUser": who, "ruleset": os.environ.get("RULESET_VERSION", ""),
    })
    return summary


def handler(event: dict, _context) -> dict:
    """POST /morning — decide every school, persist to DynamoDB, alert, ledger."""
    role = cognito_role(event)
    if role != "officer":
        return respond(403, {"detail": f"role {role} cannot run:morning"})
    who = principal_id(event)
    return respond(200, {"ok": True, "by": who, **_run(who)})


def schedule_handler(event: dict, _context) -> dict:
    """EventBridge-scheduled run (06:00 IST). Refreshes live sources, then runs."""
    refreshed: dict = {}
    if os.environ.get("SOURCE_MODE", "frozen") == "live":
        refreshed = {
            "stations": refresh_air_dyn(),
            "fires": refresh_fires_dyn(),
        }
    who = "system@firstlight"
    return respond(200, {
        "ok": True, "by": who, "trigger": "eventbridge", "refreshed": refreshed, **_run(who),
    })


def status_handler(event: dict, _context) -> dict:
    """GET /status?schoolId=... — latest decision for a school."""
    params = event.get("queryStringParameters") or {}
    school_id = params.get("schoolId", "")
    if not school_id:
        return respond(400, {"error": "schoolId is required"})
    decision = get_latest(school_id)
    if decision is None:
        return respond(404, {"error": f"no decision for {school_id}"})
    return respond(200, {"schoolId": school_id, "decision": decision})

