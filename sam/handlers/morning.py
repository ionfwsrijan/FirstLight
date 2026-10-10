"""Ship It mirror of FIRSTLIGHT pipeline/morning.py.

Uses the frozen scenario for date 2026-10-08 (same as the local build) so the
demo and the deployed twin show identical verdicts. The run is gated to the
officer role (mirroring the local "run:morning" capability) and every decision,
alert and the run itself is appended to the hash-chained LEDGER collection.
"""

from __future__ import annotations

import os

from firstlight.agent import narrate, sign
from firstlight.engine import decide_all
from firstlight.pipeline.scenario import morning_inputs

try:
    from .shared import (
        append_ledger,
        cognito_role,
        get_latest,
        notify_webhook,
        now_utc,
        principal_id,
        put_alert,
        put_decision,
        respond,
    )
except ImportError:  # Lambda treats handlers/ as the code root (no package parent)
    from shared import (
        append_ledger,
        cognito_role,
        get_latest,
        notify_webhook,
        now_utc,
        principal_id,
        put_alert,
        put_decision,
        respond,
    )


def handler(event: dict, _context) -> dict:
    """POST /morning — decide every school, persist to DynamoDB, alert, ledger."""
    role = cognito_role(event)
    if role != "officer":
        return respond(403, {"detail": f"role {role} cannot run:morning"})

    inputs = morning_inputs()
    who = principal_id(event)

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

    return respond(200, {"ok": True, "by": who, **summary})


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
